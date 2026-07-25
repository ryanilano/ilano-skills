#!/usr/bin/env python3
"""headroom - read Claude subscription caps across accounts and say what to do.

Security contract (see SKILL.md):
  - OAuth tokens are read from the macOS Keychain, held in a local variable,
    sent in exactly one Authorization header, and never printed, logged,
    cached, or placed in argv.
  - Output carries derived numbers only: profile name, cap kind, percent,
    reset time, pacing, verdict, credential state. No tokens, no emails.
  - Network egress is a single host: api.anthropic.com.

Status messages go to stderr. JSON goes to stdout.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import ssl
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

if sys.version_info < (3, 8):  # stdlib only; no third-party imports anywhere
    sys.exit("headroom needs Python 3.8 or newer")

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
ALLOWED_HOST = "api.anthropic.com"
OAUTH_BETA = "oauth-2025-04-20"

KEYCHAIN_TIMEOUT = 3  # `security` can hang on macOS 26; TokenEater issue #217
HTTP_TIMEOUT = 10  # a model-invoked skill must not stall the session

SCHEMA_VERSION = 1  # closed output schema; redaction is auditable against it

CACHE_DIR = os.path.expanduser("~/.cache/headroom")
TTL_NORMAL = 300
TTL_URGENT = 60

# Window lengths keyed by the API's `group` field.
WINDOW = {"session": timedelta(hours=5), "weekly": timedelta(days=7)}

# Thresholds. `WALL` matches the severity break the other tools already use.
WALL_PCT = 85
EASE_PACING = 10
BURN_PACING = -20

APPLE_EPOCH_OFFSET = 978307200  # TokenEater timestamps are Core Foundation epoch


def log(msg):
    print(msg, file=sys.stderr)


def now_utc():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- roster


def _expand(config_dir):
    """Relative names join against $HOME, never the cwd.

    abspath, not realpath: the Keychain service name is derived from the
    unresolved absolute path, and these dirs contain symlinked subdirectories.
    """
    if config_dir.startswith("/"):
        return os.path.abspath(config_dir.rstrip("/"))
    if config_dir.startswith("~"):
        return os.path.abspath(os.path.expanduser(config_dir).rstrip("/"))
    home = os.path.expanduser("~")
    return os.path.abspath(os.path.join(home, config_dir.rstrip("/")))


def _under_home(path):
    """profiles.json is written by other tools, so treat it as untrusted.

    An unvalidated config_dir would be an arbitrary-file-read primitive once
    doctor mode opens <config_dir>/settings.json.
    """
    home = os.path.abspath(os.path.expanduser("~"))
    if ".." in path.split(os.sep):
        return False
    return path == home or path.startswith(home + os.sep)


def _safe_label(value, limit=48):
    """Constrain roster strings before they reach output.

    `profile` and `wrapper` come from profiles.json and are surfaced to the
    model, including as a command to run. The same rule that governs doctor
    output applies here: text from a file other tools write must not be
    repeated into context as if it were trustworthy. Nothing is executed
    either way (every subprocess call uses a fixed argv list), but an
    unconstrained label is still an injection channel.

    Rejected rather than scrubbed: stripping metacharacters would still let
    an instruction-shaped sentence through, and prose is the injection vector
    that matters for a model. A label is either a plain identifier or it is
    replaced wholesale.
    """
    if not isinstance(value, str) or not value:
        return "invalid"
    if len(value) > limit or not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        return "invalid"
    return value


def _tilde(path):
    """Display form. Absolute paths publish the account name into transcripts."""
    home = os.path.abspath(os.path.expanduser("~"))
    if path == home:
        return "~"
    if path.startswith(home + os.sep):
        return "~" + path[len(home) :]
    return path


def load_profiles():
    """Account roster from maxx's profiles.json, else discovered config dirs.

    Reading the roster at runtime is deliberate: nothing that identifies an
    account is ever written into this repo.
    """
    base = os.environ.get("MAXX_CONFIG_DIR") or os.path.expanduser("~/.config/maxx")
    path = os.path.join(base, "profiles.json")
    profiles = []
    if os.path.isfile(path):
        try:
            with open(path) as fh:
                data = json.load(fh)
            # Type-guard every level. This file is written by other tools, so
            # a wrong shape is an expected input, not an exceptional one: a
            # bare `null`, a list, or a non-string field must degrade to
            # discovery rather than raise.
            if not isinstance(data, dict):
                raise TypeError("profiles.json is not an object")
            listed = data.get("profiles")
            if not isinstance(listed, list):
                raise TypeError("profiles.json has no profiles list")
            for entry in listed:
                if not isinstance(entry, dict):
                    continue
                if entry.get("tool", "claude") != "claude":
                    continue
                name = entry.get("name")
                cfg = entry.get("config_dir")
                if not isinstance(name, str) or not isinstance(cfg, str):
                    continue
                if not name or not cfg:
                    continue
                resolved = _expand(cfg)
                if not _under_home(resolved):
                    log("warn: skipping profile %r (config_dir outside home)" % name)
                    continue
                # `wrapper` and `tool` are command names and are never executed.
                wrapper = entry.get("wrapper")
                if not isinstance(wrapper, str) or not wrapper:
                    wrapper = "claude-%s" % name
                profiles.append(
                    {
                        "name": _safe_label(name),
                        "config_dir": resolved,
                        "wrapper": _safe_label(wrapper),
                        "source": "maxx",
                    }
                )
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            log("warn: could not parse %s (%s)" % (_tilde(path), type(exc).__name__))

    if profiles:
        return profiles

    # Discovery fallback. Only real config dirs count: `~/.claude.json` is a
    # file, `~/.claude-plugin` is not an account, and backup copies would
    # otherwise trigger pointless Keychain lookups (each a possible prompt).
    home = os.path.expanduser("~")
    try:
        entries = sorted(os.listdir(home))
    except OSError:
        return profiles
    for entry in entries:
        if not entry.startswith(".claude") or len(profiles) >= 8:
            continue
        full = os.path.join(home, entry)
        if not os.path.isdir(full) or os.path.islink(full):
            continue
        looks_like_config = os.path.isfile(
            os.path.join(full, "settings.json")
        ) or os.path.isfile(os.path.join(full, ".credentials.json"))
        if not looks_like_config:
            continue
        profiles.append(
            {
                "name": _safe_label(entry[1:]),  # ".claude-fyi" -> "claude-fyi"
                "config_dir": full,
                "wrapper": "claude",
                "source": "discovered",
            }
        )
    return profiles


# ------------------------------------------------------------ credentials


def keychain_service(config_dir):
    digest = hashlib.sha256(os.path.abspath(config_dir).encode()).hexdigest()[:8]
    return "Claude Code-credentials-%s" % digest


def _from_keychain(config_dir):
    """macOS only. Verified working against live Claude Code installs."""
    services = [keychain_service(config_dir)]
    if os.path.abspath(config_dir) == os.path.expanduser("~/.claude"):
        services.append("Claude Code-credentials")  # legacy unsuffixed entry

    for index, service in enumerate(services):
        try:
            # Read-only. No -A, no ACL modification, no write subcommands.
            # The service name is a truncated hash, so argv carries no secret;
            # the credential comes back on stdout and never touches argv.
            proc = subprocess.run(
                ["security", "find-generic-password", "-s", service, "-w"],
                capture_output=True,
                text=True,
                timeout=KEYCHAIN_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            # Distinct from signed-out on purpose: a Keychain prompt on screen
            # guarantees this timeout, and calling it a logout would tell you
            # to re-authenticate a perfectly healthy account.
            return None, "keychain-timeout", None
        except OSError:
            return None, "security-unavailable", None
        if proc.returncode == 0 and proc.stdout.strip():
            # Flag the legacy unsuffixed hit so the ambiguity is visible.
            return proc.stdout.strip(), None, ("legacy-unsuffixed" if index else None)
    return None, None, None  # no entry, not an error


def _from_file(config_dir):
    """Linux and Windows keep credentials in a file beside the config.

    UNVERIFIED on this machine: macOS installs store nothing here, so the
    exact shape could not be confirmed locally. The parser below accepts the
    documented `claudeAiOauth` wrapper and also a bare token object, and any
    other shape degrades to `unreadable` rather than guessing.
    """
    path = os.path.join(config_dir, ".credentials.json")
    if not os.path.isfile(path):
        return None, None, None
    try:
        with open(path) as fh:
            return fh.read(), None, None
    except OSError:
        return None, "credentials-unreadable", None


def _from_env(profile_name):
    """Escape hatch for platforms neither source covers.

    Must be an OAuth login credential: `claude setup-token` output is
    inference-scoped and the usage endpoint rejects it with 403
    (`does not meet scope requirement any_of(user:profile)`).
    """
    key = "HEADROOM_TOKEN_%s" % re.sub(r"[^A-Za-z0-9]", "_", profile_name).upper()
    token = os.environ.get(key)
    if not token:
        return None, None, None
    return json.dumps({"claudeAiOauth": {"accessToken": token}}), None, "env"


def billing_mode(config_dir):
    """Detect setups that have no subscription caps to report.

    This skill only covers Claude bought directly from Anthropic as a
    Pro/Max subscription. Claude Code can also bill through AWS Bedrock,
    Google Vertex, or a pay-as-you-go API key, and none of those have a
    5-hour or weekly subscription window. Reporting them as `signed-out`
    would be wrong, so they get their own state.

    Returns a closed enum, never the value of any environment variable.
    """
    markers = {
        "CLAUDE_CODE_USE_BEDROCK": "bedrock",
        "CLAUDE_CODE_USE_VERTEX": "vertex",
        "ANTHROPIC_API_KEY": "api-key",
        "ANTHROPIC_AUTH_TOKEN": "api-key",
    }

    # Only the explicit Bedrock/Vertex switches are trusted from the ambient
    # environment. ANTHROPIC_API_KEY is commonly exported for unrelated SDK
    # work while Claude Code still authenticates with a subscription, so
    # treating it as ambient proof would misreport a healthy account.
    for key in ("CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX"):
        value = os.environ.get(key)
        if value and value not in ("0", "false", "False"):
            return markers[key]

    path = os.path.join(config_dir, "settings.json")
    try:
        with open(path) as fh:
            env = (json.load(fh) or {}).get("env") or {}
    except (OSError, ValueError, AttributeError):
        return None
    if not isinstance(env, dict):
        return None
    for key, mode in markers.items():
        value = env.get(key)
        if value and value not in ("0", "false", "False"):
            return mode
    return None


def read_credential(config_dir, profile_name="default"):
    """Return (state, token, meta). The token is never logged or cached.

    state is one of: fresh, stale, signed-out, missing, unreadable.
    Sources are tried in order of trustworthiness for the running platform.
    """
    sources = []
    if sys.platform == "darwin":
        sources.append(("keychain", lambda: _from_keychain(config_dir)))
    sources.append(("file", lambda: _from_file(config_dir)))
    sources.append(("env", lambda: _from_env(profile_name)))

    raw, source, note, problem = None, None, None, None
    for name, getter in sources:
        candidate, err, flag = getter()
        if err:
            problem = err
            continue
        if candidate:
            raw, source, note = candidate, name, flag
            break

    if raw is None:
        if problem == "keychain-timeout":
            return "keychain-timeout", None, {"reason": problem, "source": None}
        if problem:
            return "unreadable", None, {"reason": problem, "source": None}
        return "missing", None, {"reason": "no stored credential", "source": None}

    try:
        parsed = json.loads(raw)
    except ValueError:
        # Never surface the payload itself, only that it did not parse.
        return (
            "unreadable",
            None,
            {"reason": "credential payload is not valid JSON", "source": source},
        )
    finally:
        del raw

    if isinstance(parsed, dict) and isinstance(parsed.get("claudeAiOauth"), dict):
        blob = parsed["claudeAiOauth"]
    elif isinstance(parsed, dict) and "accessToken" in parsed:
        blob = parsed  # tolerate an unwrapped object
    else:
        return (
            "unreadable",
            None,
            {"reason": "unrecognized credential shape", "source": source},
        )

    token = blob.get("accessToken")

    def to_dt(ms):
        if not ms:
            return None
        try:
            return datetime.fromtimestamp(ms / 1000, timezone.utc)
        except (OSError, OverflowError, ValueError, TypeError):
            return None

    access_dt = to_dt(blob.get("expiresAt"))
    refresh_dt = to_dt(blob.get("refreshTokenExpiresAt"))

    # Deliberately coarse. Exact expiry timestamps are a credential-lifecycle
    # fingerprint, and they would be written permanently into transcripts.
    # `scopes` and `subscriptionType` are account metadata the advice does not
    # consume, so they are never read into the result at all.
    meta = {"source": source, "note": note}

    now = now_utc()
    skew = timedelta(minutes=5)  # tolerate modest clock drift either way
    if token and access_dt and access_dt > now + skew:
        return "fresh", token, meta
    if token and access_dt and access_dt > now - skew:
        return "expiring", token, meta
    if refresh_dt and refresh_dt > now:
        # Recoverable: Claude Code refreshes on next launch. Not a logout.
        return "stale", None, meta
    return "signed-out", None, meta


# --------------------------------------------------------------- network


class _SameHostRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse any redirect that would leave the single allowed host.

    urllib re-sends Request-supplied headers across redirects, so an
    unconstrained redirect would carry the bearer token to another host.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        # Scheme is checked as well as host: urllib would otherwise permit a
        # redirect to http://api.anthropic.com, sending the bearer token in
        # cleartext.
        if target.hostname != ALLOWED_HOST or target.scheme != "https":
            raise urllib.error.URLError("refusing unsafe redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _tls_context():
    """Build the context explicitly so SSLKEYLOGFILE is never honored.

    ssl.create_default_context() reads SSLKEYLOGFILE from the environment and
    writes TLS master secrets there, which would let anyone with a packet
    capture decrypt the Authorization header. Constructing the context
    directly skips that branch. Verification stays on unconditionally.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.load_default_certs()
    return ctx


def fetch_usage(token):
    """One GET to one host. Errors never echo headers, body, or the token."""
    parts = urlsplit(USAGE_URL)
    # Asserted immediately before the request: a diff that mutates USAGE_URL
    # to an exfiltration endpoint fails here instead of silently succeeding.
    if parts.scheme != "https" or parts.hostname != ALLOWED_HOST:
        return None, "refusing request to unexpected endpoint"

    req = urllib.request.Request(
        USAGE_URL,
        headers={
            "Authorization": "Bearer %s" % token,
            "anthropic-beta": OAUTH_BETA,
            "Accept": "application/json",
        },
    )
    opener = urllib.request.build_opener(
        _SameHostRedirect, urllib.request.HTTPSHandler(context=_tls_context())
    )
    try:
        with opener.open(req, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode()), None
    except urllib.error.HTTPError as exc:
        # Status only. The body can echo the request and is remote-controlled.
        return None, "http %s" % exc.code
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", "unreachable")
        return None, "network error (%s)" % type(reason).__name__
    except (ValueError, OSError):
        return None, "response was not valid JSON"


# ----------------------------------------------------------------- caps


def parse_reset(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def extract_caps(data):
    """`limits[]` is authoritative; flat buckets are the legacy fallback.

    The trap this guards: limits[] entries use `percent`, flat buckets use
    `utilization`. Mixing them silently drops caps (all-caps POSTMORTEM
    2026-07-19). A null utilization is unknown, never zero.
    """
    caps = []
    for lim in data.get("limits") or []:
        pct = lim.get("percent")
        if pct is None:
            continue
        scope = lim.get("scope") or {}
        model = (scope.get("model") or {}).get("display_name")
        caps.append(
            {
                "kind": lim.get("kind") or "unknown",
                "group": lim.get("group") or "weekly",
                "percent": float(pct),
                "model": model,
                "resets_at": lim.get("resets_at"),
                "severity": lim.get("severity"),
                "binding": bool(lim.get("is_active")),
            }
        )
    if caps:
        return caps

    for key, group in (("five_hour", "session"), ("seven_day", "weekly")):
        bucket = data.get(key)
        if not isinstance(bucket, dict):
            continue
        util = bucket.get("utilization")
        if util is None:
            continue
        caps.append(
            {
                "kind": key,
                "group": group,
                "percent": float(util),
                "model": None,
                "resets_at": bucket.get("resets_at"),
                "severity": None,
                "binding": False,
            }
        )
    return caps


def enrich(cap):
    """Add time-to-reset, elapsed fraction, pacing, and a verdict.

    pacing = percent - elapsed%, where the window start is derived as
    resets_at - window_length. Verified against TokenEater: -61.7% computed
    vs -61% displayed for the weekly window.
    """
    reset = parse_reset(cap.get("resets_at"))
    length = WINDOW.get(cap["group"])
    cap["seconds_left"] = None
    cap["elapsed_pct"] = None
    cap["pacing"] = None

    if reset and length:
        now = now_utc()
        start = reset - length
        total = length.total_seconds()
        elapsed = (now - start).total_seconds()
        frac = max(0.0, min(1.0, elapsed / total)) if total else 0.0
        cap["seconds_left"] = max(0.0, (reset - now).total_seconds())
        cap["elapsed_pct"] = round(frac * 100, 1)
        cap["pacing"] = round(cap["percent"] - frac * 100, 1)

    pct, pacing = cap["percent"], cap["pacing"]
    if pct >= WALL_PCT:
        cap["verdict"] = "wall"
    elif pacing is None:
        cap["verdict"] = "steady"
    elif pacing >= EASE_PACING:
        cap["verdict"] = "ease"
    elif pacing <= BURN_PACING:
        cap["verdict"] = "burn"
    else:
        cap["verdict"] = "steady"
    return cap


def binding_cap(caps):
    """The cap the API flags as binding, else the highest percent."""
    for cap in caps:
        if cap.get("binding"):
            return cap
    return max(caps, key=lambda c: c["percent"]) if caps else None


# ---------------------------------------------------------------- cache


def _cache_path(profile_name):
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", profile_name)
    return os.path.join(CACHE_DIR, "%s.json" % safe)


def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, mode=0o700, exist_ok=True)
    try:
        os.chmod(CACHE_DIR, 0o700)
    except OSError:
        pass


def cache_ttl(caps):
    for cap in caps:
        if cap["percent"] >= WALL_PCT:
            return TTL_URGENT
        left = cap.get("seconds_left")
        if left is not None and 0 < left < 900:
            return TTL_URGENT
    return TTL_NORMAL


def read_cache(profile_name):
    path = _cache_path(profile_name)
    try:
        with open(path) as fh:
            payload = json.load(fh)
    except (OSError, ValueError):
        return None

    stored = payload.get("stored_at", 0)
    caps = payload.get("caps") or []
    age = now_utc().timestamp() - stored
    if age > cache_ttl(caps):
        return None
    # Never serve a cap whose own reset has already passed.
    for cap in caps:
        reset = parse_reset(cap.get("resets_at"))
        if reset and reset <= now_utc():
            return None
    return caps


def write_cache(profile_name, caps):
    """Derived numbers only. No credential material reaches this file."""
    _ensure_cache_dir()
    path = _cache_path(profile_name)
    payload = {"stored_at": now_utc().timestamp(), "caps": caps}
    tmp = path + ".tmp"
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump(payload, fh)
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(tmp, path)
    except OSError as exc:
        log("warn: cache write failed (%s)" % type(exc).__name__)
        try:
            os.unlink(tmp)
        except OSError:
            pass


# -------------------------------------------------------------- gather


def gather(profiles, refresh=False):
    results = []
    for prof in profiles:
        entry = {
            "profile": prof["name"],
            "wrapper": prof["wrapper"],
            "caps": [],
            "binding": None,
            "cached": False,
        }
        mode = billing_mode(prof["config_dir"])
        if mode:
            entry["credential"] = "not-subscription"
            entry["billing"] = mode
            entry["recovery"] = (
                "this profile bills through %s, which has no 5-hour or weekly "
                "subscription window to report" % mode
            )
            results.append(entry)
            continue

        state, token, meta = read_credential(prof["config_dir"], prof["name"])
        entry["credential"] = state
        if meta.get("note"):
            entry["credential_note"] = meta["note"]

        if token is None:
            entry["recovery"] = {
                # Verified: `claude auth status` reads local state and does
                # NOT refresh. The token is renewed on the next authenticated
                # request, so a real session is what recovers this.
                "stale": "start a session with `%s`; the token refreshes on "
                "its next authenticated request" % prof["wrapper"],
                "signed-out": "run `CLAUDE_CONFIG_DIR=%s claude auth login` "
                "in a real terminal" % _tilde(prof["config_dir"]),
                "missing": "this profile has never been signed in",
                "keychain-timeout": "the keychain did not answer; a permission "
                "prompt may be waiting on screen",
                "unreadable": "credential could not be read",
            }.get(state, "unknown credential state")
            results.append(entry)
            continue

        caps = None if refresh else read_cache(prof["name"])
        if caps is not None:
            entry["cached"] = True
        else:
            data, err = fetch_usage(token)
            del token
            if err:
                entry["error"] = err
                results.append(entry)
                continue
            caps = [enrich(c) for c in extract_caps(data)]
            write_cache(prof["name"], caps)

        entry["caps"] = caps
        binding = binding_cap(caps)
        entry["binding"] = binding["kind"] if binding else None
        entry["binding_percent"] = binding["percent"] if binding else None
        entry["verdict"] = binding["verdict"] if binding else None
        results.append(entry)
    return results


def recommend(results):
    """Which account to run on, and why. Profile names only, never emails."""
    usable = [r for r in results if r.get("caps")]
    if not usable:
        return {
            "account": None,
            "reason": "no account returned usage; fix credentials first",
        }

    best = min(usable, key=lambda r: r.get("binding_percent") or 0)
    binding = binding_cap(best["caps"])
    reason = "binding cap is %s at %.0f%%" % (binding["kind"], binding["percent"])
    if binding.get("model"):
        reason += " (%s)" % binding["model"]

    expiring = []
    for res in usable:
        for cap in res["caps"]:
            left = cap.get("seconds_left")
            if (
                cap["group"] == "weekly"
                and left is not None
                and left < 12 * 3600
                and cap["percent"] < 60
            ):
                expiring.append(
                    {
                        "profile": res["profile"],
                        "kind": cap["kind"],
                        "unused_percent": round(100 - cap["percent"], 1),
                        "hours_left": round(left / 3600, 1),
                    }
                )

    return {
        "account": best["profile"],
        "wrapper": best["wrapper"],
        "reason": reason,
        "verdict": best.get("verdict"),
        "expiring_soon": expiring,
    }


# -------------------------------------------------------------- doctor


def _hook_present(config_dir, needle):
    """True if a hook command mentions `needle`. Content is never returned."""
    path = os.path.join(config_dir, "settings.json")
    try:
        with open(path) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    for entries in (data.get("hooks") or {}).values():
        for matcher in entries or []:
            for hook in matcher.get("hooks") or []:
                if needle in str(hook.get("command", "")):
                    return True
    return False


def _process_running(exact_name):
    """Exit status only, matched on the exact process name.

    `pgrep -f` would match full command lines, and printing its output would
    dump other processes' argv, which routinely carries other tools' secrets.
    Only the boolean ever leaves this function.
    """
    if not shutil.which("pgrep"):
        return None
    try:
        proc = subprocess.run(
            ["pgrep", "-x", exact_name], capture_output=True, text=True, timeout=5
        )
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return None


def doctor(profiles, results):
    """Presence and absence only. No file contents cross into output."""
    checks = []

    for res in results:
        state = res["credential"]
        healthy = state in ("fresh", "expiring")
        checks.append(
            {
                "check": "credential:%s" % res["profile"],
                "status": "ok" if healthy else "warn",
                "detail": state
                if healthy
                else "%s; %s" % (state, res.get("recovery", "")),
            }
        )

    # rtk is only probed when the local config actually references it, because
    # a different project ships an unrelated binary of the same name and this
    # skill must never run an arbitrary PATH binary on a stranger's machine.
    rtk_referenced = any(_hook_present(p["config_dir"], "rtk hook") for p in profiles)
    rtk_path = shutil.which("rtk")
    if not rtk_referenced:
        checks.append(
            {"check": "rtk", "status": "ok", "detail": "not configured; skipped"}
        )
    elif not rtk_path:
        checks.append(
            {"check": "rtk:binary", "status": "fail", "detail": "not on PATH"}
        )
    else:
        try:
            proc = subprocess.run(
                [rtk_path, "--version"], capture_output=True, text=True, timeout=5
            )
            ok = proc.returncode == 0
            # Version string only. `rtk gain` is usage analytics over your
            # history, not a health check, so it is never invoked here.
            detail = proc.stdout.strip()[:40] if ok else "not runnable"
        except (subprocess.TimeoutExpired, OSError):
            ok, detail = False, "did not respond"
        checks.append(
            {"check": "rtk:binary", "status": "ok" if ok else "fail", "detail": detail}
        )

    for prof in profiles:
        present = _hook_present(prof["config_dir"], "rtk hook")
        checks.append(
            {
                "check": "rtk:hook:%s" % prof["name"],
                "status": "ok" if present else ("warn" if present is False else "warn"),
                "detail": "hook registered" if present else "no rtk hook registered",
            }
        )
        rtk_doc = os.path.isfile(os.path.join(prof["config_dir"], "RTK.md"))
        claude_md = os.path.isfile(os.path.join(prof["config_dir"], "CLAUDE.md"))
        if claude_md and not rtk_doc:
            checks.append(
                {
                    "check": "rtk:doc:%s" % prof["name"],
                    "status": "warn",
                    "detail": "CLAUDE.md present but RTK.md missing; "
                    "an @RTK.md import would not resolve here",
                }
            )

    if sys.platform != "darwin":
        # TokenEater and CodeBurn are macOS apps; probing for them elsewhere
        # would report a misleading "not running".
        return checks

    te_running = _process_running("TokenEater")
    te_path = os.path.expanduser(
        "~/Library/Application Support/com.tokeneater.shared/shared.json"
    )
    te_detail = "not running"
    te_status = "warn"
    if te_running:
        age_min = None
        try:
            with open(te_path) as fh:
                shared = json.load(fh)
            fetched = (shared.get("cachedUsage") or {}).get("fetchDate")
            if fetched:
                when = datetime.fromtimestamp(
                    fetched + APPLE_EPOCH_OFFSET, timezone.utc
                )
                age_min = (now_utc() - when).total_seconds() / 60
        except (OSError, ValueError, TypeError):
            age_min = None
        if age_min is None:
            te_detail, te_status = "running; cache unreadable", "warn"
        elif age_min < 30:
            te_detail = "running; cache %.0f min old" % age_min
            te_status = "ok"
        else:
            te_detail = "running; cache stale (%.0f min)" % age_min
            te_status = "warn"
    checks.append({"check": "tokeneater", "status": te_status, "detail": te_detail})

    cb_running = _process_running("CodeBurn")
    checks.append(
        {
            "check": "codeburn",
            "status": "warn",
            "detail": "running; no evidence of recording"
            if cb_running
            else "not running",
        }
    )

    return checks


# --------------------------------------------------------------- output


def fmt_countdown(seconds):
    if seconds is None:
        return "?"
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    mins = rem // 60
    if days:
        return "%dd %dh" % (days, hours)
    if hours:
        return "%dh %02dm" % (hours, mins)
    return "%dm" % mins


def bar(pct, width=24):
    filled = int(round(min(100.0, max(0.0, pct)) / 100 * width))
    return "█" * filled + "░" * (width - filled)


def render(results, advice, checks=None):
    out = []
    out.append("Claude headroom - %s" % now_utc().astimezone().strftime("%a %b %d, %-I:%M %p"))
    for res in results:
        out.append("")
        label = res["profile"]
        if res.get("recovery"):
            out.append("  %s: %s" % (label, res["credential"]))
            out.append("      %s" % res["recovery"])
            continue
        if res.get("error"):
            out.append("  %s: %s" % (label, res["error"]))
            continue
        suffix = " (cached)" if res.get("cached") else ""
        out.append("  %s%s" % (label, suffix))
        for cap in res["caps"]:
            name = cap["kind"]
            if cap.get("model"):
                name += ":%s" % cap["model"]
            mark = " <- binding" if cap.get("binding") else ""
            pacing = "" if cap["pacing"] is None else "  pacing %+.0f%%" % cap["pacing"]
            out.append(
                "    %-22s %s %5.1f%%  resets %s%s%s"
                % (
                    name,
                    bar(cap["percent"]),
                    cap["percent"],
                    fmt_countdown(cap["seconds_left"]),
                    pacing,
                    mark,
                )
            )

    out.append("")
    if advice.get("account"):
        out.append("  run on: %s (%s)" % (advice["account"], advice["reason"]))
        if advice.get("wrapper"):
            out.append("  command: %s" % advice["wrapper"])
        for item in advice.get("expiring_soon") or []:
            out.append(
                "  note: %s has %.0f%% of its %s unused with %.1fh left"
                % (
                    item["profile"],
                    item["unused_percent"],
                    item["kind"],
                    item["hours_left"],
                )
            )
    else:
        out.append("  %s" % advice.get("reason", "no recommendation"))

    if checks:
        out.append("")
        out.append("  monitoring")
        for chk in checks:
            symbol = {"ok": "ok  ", "warn": "warn", "fail": "FAIL"}.get(
                chk["status"], "?   "
            )
            out.append("    %s %-26s %s" % (symbol, chk["check"], chk["detail"]))
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(
        description="Report Claude subscription headroom across accounts."
    )
    parser.add_argument("--json", action="store_true", help="emit JSON on stdout")
    parser.add_argument("--refresh", action="store_true", help="bypass the cache")
    parser.add_argument(
        "--doctor", action="store_true", help="verify the monitoring stack"
    )
    args = parser.parse_args()

    if sys.platform != "darwin":
        # Keychain is macOS-only, but the file and env sources are not, so
        # other platforms degrade instead of failing. The file layout is
        # unverified here; see _from_file.
        log("note: not macOS; reading credentials from file or env only")

    profiles = load_profiles()
    if not profiles:
        # A stranger with no Claude config gets a clean empty result, not an
        # error and not a scan of their home directory.
        empty = {"schema": SCHEMA_VERSION, "accounts": [], "advice": None}
        print(json.dumps(empty, indent=2) if args.json else "No Claude profiles found.")
        return 0

    results = gather(profiles, refresh=args.refresh)
    advice = recommend(results)
    checks = doctor(profiles, results) if args.doctor else None

    if args.json:
        payload = {
            "schema": SCHEMA_VERSION,
            "generated_at": now_utc().isoformat(timespec="seconds"),
            "accounts": results,
            "advice": advice,
        }
        if checks is not None:
            payload["monitoring"] = checks
        print(json.dumps(payload, indent=2))
    else:
        print(render(results, advice, checks))

    if checks and any(c["status"] == "fail" for c in checks):
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001 - deliberate catch-all
        # A raw traceback prints absolute source paths (publishing the account
        # name) and, with a locals-rendering handler installed, could print
        # variable values. Fail with one line naming only the exception type.
        log("error: unexpected failure (%s)" % type(exc).__name__)
        sys.exit(1)
