# tool-call-repair, explained for people

An AI agent calls a tool by sending JSON that has to match a schema exactly. Cheaper
and open models often get it almost right: `null` where the field should be left out,
a list sent as a string, a bare word where a list of one was wanted, a file path that
got turned into a markdown link. A strict harness rejects the call and the model gets
blamed for being "bad at tools". Usually the harness is the problem.

## What it does

It validates the model's input against the schema first. If it is valid, nothing is
touched. If it is not, it looks at exactly where the schema disagreed and applies one
of five small, known repairs at that spot. If the input still does not validate, it
returns a message the model can read and fix itself next turn.

## The five repairs

1. `null` for an optional field becomes the field being omitted.
2. A string that contains a JSON list becomes the list.
3. An empty object where a list was wanted becomes an empty list.
4. A bare string where a list was wanted becomes a one-item list.
5. A path that arrived as `[notes.md](http://notes.md)` becomes `notes.md`.

## Why validate first and repair second

If you clean up input before checking it, you corrupt valid data that only looks
broken. A file whose contents happen to be JSON-shaped is the classic case. Repairing
only at the paths the validator flagged means correct input is never changed.

## Why the order of repairs matters

The list-in-a-string repair runs before the wrap-in-a-list repair. Done the other way
round, a string containing a list would be wrapped into a list containing that string.
The schema would be satisfied and the meaning would be lost.

## Where the idea comes from

The technique and the catalog were published by Ahmad Awais in the Command Code
write-up on tool call repairs. This is an independent Python reimplementation of the
documented method. It uses no Command Code source.

## Requirements

Python 3, standard library only. The tests run offline in under a second.
