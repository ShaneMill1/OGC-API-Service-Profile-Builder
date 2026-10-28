# Demo — requirements vs. recommendations

A short, reproducible walkthrough of how the profile builder treats the three
RFC 2119 statement levels — **requirement (SHALL)**, **recommendation
(SHOULD)**, **permission (MAY)** — and why only requirements are
conformance-tested.

The story: the author sets one field, `level`, and everything downstream
follows — the Metanorma block type, the identifier namespace, the generated
filename, the quality summary, and whether the statement is conformance-tested.

## Demo assets

Three near-identical minimal profiles in `examples/demo_level/` that differ by
(essentially) one line:

| File | The `temperature-units-label` statement |
|---|---|
| `minimal_baseline.yaml` | absent (control) |
| `minimal_recommendation.yaml` | present, `level: recommendation` |
| `minimal_requirement.yaml` | present, `level: requirement` |

`minimal_recommendation.yaml` and `minimal_requirement.yaml` differ by exactly
one substantive line: `level: recommendation` vs `level: requirement`.

## Pre-build before the meeting

The `--pdf` step runs Metanorma in Docker and takes a few minutes, so build the
PDFs ahead of time:

```bash
for v in baseline recommendation requirement; do
  oapi-profile-builder generate \
    --config examples/demo_level/minimal_$v.yaml \
    --output /tmp/demo_$v --pdf
done
```

(Drop `--pdf` for an instant run that still shows the AsciiDoc + quality summary.)

## Live flow (~8 minutes)

### 1. One field controls it — show the config diff

```bash
diff examples/demo_level/minimal_recommendation.yaml \
     examples/demo_level/minimal_requirement.yaml
```

The only substantive change is `level: recommendation` → `level: requirement`.
Say: "Same id, same wording, same parts. The author changes intent with one
field. Watch what that one line does."

### 2. Generate and read the quality summary

```bash
oapi-profile-builder generate --config examples/demo_level/minimal_recommendation.yaml --output /tmp/demo_recommendation
```

The tool prints:

```
requirements    (SHALL) : 1  [conformance-tested]
recommendations (SHOULD): 1  [informative]
permissions     (MAY)   : 0  [informative]
```

Say: "Recommendations are counted and labeled **informative** — not
conformance-tested."

### 3. The level drives the identifier, block type and filename

```bash
cat /tmp/demo_recommendation/requirements/core/REC_temperature-units-label.adoc
```

```
[recommendation]
====
[%metadata]
identifier:: /rec/minimal_recommendation/temperature-units-label
...
```

Say: "`req` → `[requirement]` + `/req/` + `REQ_` file; `rec` → `[recommendation]`
+ `/rec/` + `REC_`; `may` → `[permission]` + `/per/` + `PER_`. Three separate
namespaces — a requirement and a recommendation can even share a name in one
class."

### 4. The punchline — the conformance class

```bash
grep 'abstract-test::' /tmp/demo_recommendation/abstract_tests/ATS_class_core.adoc
```

There's one `abstract-test::` line — for the requirement only. The
recommendation is deliberately **absent** from the conformance class.

Say: "This is the whole point. Conformance is assessed against SHALL only. The
tool enforces it — you can't accidentally gate conformance on a SHOULD."

### 5. Flip the switch — regenerate as a requirement

```bash
oapi-profile-builder generate --config examples/demo_level/minimal_requirement.yaml --output /tmp/demo_requirement
grep -r 'identifier:: /' /tmp/demo_requirement/requirements/core/
```

The statement's identifier is now `/req/...` and the quality summary moves it to
`requirements (SHALL)`. The tool also notes the requirement has no abstract test
yet:

```
note: 1 requirement(s) have no abstract test: core/temperature-units-label
```

Say: "Promoting a recommendation to a requirement means it now needs an abstract
test to actually be conformance-checked — the tool reminds you." (The follow-on
abstract test is scaffolded, commented out, at the bottom of
`minimal_requirement.yaml`.)

### 6. Show it in the PDF

Open `/tmp/demo_recommendation/document.pdf` and `/tmp/demo_requirement/document.pdf`
side by side. The same statement renders as a **Recommendation** box in one and
a **Requirement** box in the other — distinct labels and numbering series, as in
a real OGC document — and only the requirement appears in the Annex A abstract
test suite.

## The three sentences to land

1. The author declares `level` once; the tool derives block type, identifier,
   filename, and conformance treatment from it.
2. Requirements, recommendations and permissions are distinct, standards-native
   constructs — never mislabeled.
3. Only requirements (SHALL) are conformance-tested; recommendations and
   permissions are informative by construction, enforced automatically.
