# jvmJson

**A fair, reproducible JMH shootout between the JSON libraries Kotlin/JVM developers actually reach for.**

[![Benchmark & Deploy Dashboard](https://github.com/VeldtJumper/jvmJson/actions/workflows/benchmark.yml/badge.svg)](https://github.com/VeldtJumper/jvmJson/actions/workflows/benchmark.yml)
[![Dashboard](https://img.shields.io/badge/results-live_dashboard-38bdf8)](https://veldtjumper.github.io/jvmJson/)

The published dashboard lives at **https://veldtjumper.github.io/jvmJson/**.

## What is compared

The same logical payload is serialized and deserialized with six idiomatic setups:

| Library | Variant | Version |
| --- | --- | --- |
| kotlinx.serialization | Compiler plugin, `Json` | 1.12.0 |
| Moshi | Codegen adapter generated with KSP | 1.15.2 |
| Moshi | Reflection via `KotlinJsonAdapterFactory` | 1.15.2 |
| Jackson | `jackson-module-kotlin` | 2.22.4 |
| Jackson + Blackbird | `jackson-module-blackbird` bytecode module | 2.22.4 |
| Gson | Default reflective `Gson` | 2.15.0 |

All libraries use their normal/default configuration. There is no per-library tuning beyond registering the Kotlin module or adapter, so the comparison reflects the setup a Kotlin/JVM team would typically start with.

Toolchain: **Kotlin 2.4.21**, **KSP 2.3.13**, **JDK 21**, **Gradle 8.14.4**, **JMH 1.37**.

## Workload

One deterministic `Feed` model contains users, nested addresses with geo coordinates, tags, and posts. The generator is seeded, so every run produces the same bytes.

| Payload | Users | JSON size |
| --- | ---: | ---: |
| Small | 10 | 8,343 B |
| Medium | 1,000 | 845,128 B |
| Large | 25,000 | 21,302,262 B |

For every payload, the suite measures:

- **Deserialize** — parse one JSON string into the library's own model.
- **Serialize** — write the library's own equivalent model to a JSON string.

The deserializers all receive the exact same `String` instance. The serializers all start from an equivalent in-memory object graph. The dashboard publishes a SHA-256 digest for each payload so the input can be checked independently.

## Why the comparison is fair

- All benchmarks run in one JMH process per benchmark, with a fresh JVM fork and the same heap settings.
- JMH throughput mode: **5 warmup iterations + 20 measurement iterations**, 1 second each by default.
- Every benchmark consumes its result through `Blackhole`, so the JIT cannot eliminate the work.
- The same JVM, JDK, runner image, and pinned dependency versions are used for a published run.
- Round-trip tests run before the benchmark job, so a broken adapter fails the workflow instead of producing meaningless numbers.
- The payload generator is deterministic; re-running the workflow reproduces the same input bytes.

Absolute numbers on shared GitHub runners will move between runs. The ranking and relative gaps **within one run** are the useful signal.

## Run it locally

```bash
git clone https://github.com/VeldtJumper/jvmJson.git
cd jvmJson

# Correctness first
./gradlew test

# Full run (default: 5 warmup + 20 measured iterations, 1 fork)
./gradlew jmh

# Build the static dashboard from the JMH JSON
python3 scripts/generate_dashboard.py

# View it
python3 -m http.server 8000 --directory site
# open http://localhost:8000
```

### Quick smoke run

For a fast sanity check, override the JMH settings. These numbers are for checking that the harness works, not for publishing:

```bash
./gradlew jmh \
  -Pjmh.warmupIterations=1 \
  -Pjmh.iterations=1 \
  -Pjmh.fork=0 \
  -Pjmh.timeOnIteration=1s

python3 scripts/generate_dashboard.py
```

## GitHub Actions

`.github/workflows/benchmark.yml` runs on pushes to `main`, weekly, and on manual dispatch. It:

1. Runs the round-trip tests.
2. Runs the JMH suite.
3. Generates the static dashboard with `scripts/generate_dashboard.py`.
4. Deploys `site/` to GitHub Pages.

Manual runs accept `warmup_iterations`, `measurement_iterations`, and `forks` inputs, so you can do a quick run from the Actions tab without changing the default published methodology.

The workflow uses a fixed `ubuntu-24.04` runner, Temurin JDK 21, and a pinned Gradle wrapper. Pages is deployed through the official Pages actions with `build_type: workflow`.

Pages is already enabled on this repository. If you fork the project, enable Pages with **GitHub Actions** as the source before running the workflow.

## Project layout

```text
src/main/kotlin/com/veldtjumper/jvmjson/
  BenchmarkData.kt          deterministic payload generator
  JsonEngines.kt            one configured engine per library
  PayloadStats.kt           writes payload sizes + SHA-256 metadata
  model/Models.kt           canonical, plain, and Moshi-codegen models
src/jmh/kotlin/com/veldtjumper/jvmjson/
  JsonBenchmark.kt          the JMH benchmark methods
src/test/kotlin/com/veldtjumper/jvmjson/
  JsonEnginesTest.kt        round-trip and cross-parse tests
scripts/generate_dashboard.py
site/                       generated static dashboard (not committed)
.github/workflows/benchmark.yml
```

## Reading the dashboard

- **Operations / second** is JMH's primary throughput score.
- **Time / operation** is derived as `1000 / opsPerSec`.
- **MB / second** is `payloadBytes × opsPerSec / 1,000,000`, using the exact UTF-8 payload size.
- **± error** is half the width of JMH's reported confidence interval, as a percentage of the score.

The filters switch between serialization and deserialization and between the three payload sizes. The table always shows the six libraries for the selected view, ranked by throughput.

## Caveats

This is a microbenchmark, not a verdict. It does not model schema evolution, streaming parsers, polymorphic payloads, validation, or allocation pressure in a large application heap. A library that wins here can still be the wrong choice for a codebase because of API design, Kotlin support, or generated-code trade-offs. Use the dashboard as one input, then measure your own payloads.

### Why Gson can win deserialization

Gson's default reflective adapter can allocate a class without invoking its constructor by falling back to JDK `Unsafe`. For a Kotlin data class with no no-arg constructor, that skips Kotlin constructor invocation and null checks, and Gson can even leave a non-null Kotlin property null if the input is malformed. That is a real part of its deserialization advantage here; it is not just parser speed. The suite measures each library under its normal/default configuration on well-formed payloads, not equivalent validation semantics. For a semantics-matched comparison, add a Gson variant with `GsonBuilder.disableJdkUnsafe()` (and a constructor-based adapter) or compare against the Kotlin-aware libraries.

## License

MIT — see [LICENSE](LICENSE).
