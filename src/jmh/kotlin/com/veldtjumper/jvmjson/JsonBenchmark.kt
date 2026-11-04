package com.veldtjumper.jvmjson

import com.veldtjumper.jvmjson.model.CodegenFeed
import com.veldtjumper.jvmjson.model.Feed
import com.veldtjumper.jvmjson.model.PlainFeed
import com.veldtjumper.jvmjson.model.toCodegen
import com.veldtjumper.jvmjson.model.toPlain
import org.openjdk.jmh.annotations.Benchmark
import org.openjdk.jmh.annotations.BenchmarkMode
import org.openjdk.jmh.annotations.Fork
import org.openjdk.jmh.annotations.Level
import org.openjdk.jmh.annotations.Measurement
import org.openjdk.jmh.annotations.Mode
import org.openjdk.jmh.annotations.OutputTimeUnit
import org.openjdk.jmh.annotations.Param
import org.openjdk.jmh.annotations.Scope
import org.openjdk.jmh.annotations.Setup
import org.openjdk.jmh.annotations.State
import org.openjdk.jmh.annotations.Warmup
import org.openjdk.jmh.infra.Blackhole
import java.util.concurrent.TimeUnit

/**
 * One benchmark class, one payload, one engine set. Every method consumes its
 * result through JMH's Blackhole so the JIT cannot delete the work.
 */
@BenchmarkMode(Mode.Throughput)
@OutputTimeUnit(TimeUnit.SECONDS)
@Warmup(iterations = 5, time = 1, timeUnit = TimeUnit.SECONDS)
@Measurement(iterations = 20, time = 1, timeUnit = TimeUnit.SECONDS)
@Fork(1)
@State(Scope.Benchmark)
open class JsonBenchmark {
    @Param("10", "1000", "25000")
    @JvmField
    var userCount: Int = 0

    private lateinit var engines: JsonEngines
    private lateinit var json: String
    private lateinit var canonical: Feed
    private lateinit var plain: PlainFeed
    private lateinit var codegen: CodegenFeed

    @Setup(Level.Trial)
    fun setup() {
        canonical = BenchmarkData.feed(userCount)
        json = BenchmarkData.canonicalJson(canonical)
        plain = canonical.toPlain()
        codegen = canonical.toCodegen()
        engines = JsonEngines()
    }

    // ---------------------------------------------------------------------
    // Serialization: model -> JSON string
    // ---------------------------------------------------------------------

    @Benchmark
    fun kotlinxSerialize(bh: Blackhole) {
        bh.consume(engines.kotlinxJson.encodeToString(Feed.serializer(), canonical))
    }

    @Benchmark
    fun moshiReflectSerialize(bh: Blackhole) {
        bh.consume(engines.moshiReflectAdapter.toJson(plain))
    }

    @Benchmark
    fun moshiCodegenSerialize(bh: Blackhole) {
        bh.consume(engines.moshiCodegenAdapter.toJson(codegen))
    }

    @Benchmark
    fun jacksonSerialize(bh: Blackhole) {
        bh.consume(engines.jacksonMapper.writeValueAsString(plain))
    }

    @Benchmark
    fun jacksonBlackbirdSerialize(bh: Blackhole) {
        bh.consume(engines.jacksonBlackbirdMapper.writeValueAsString(plain))
    }

    @Benchmark
    fun gsonSerialize(bh: Blackhole) {
        bh.consume(engines.gson.toJson(plain))
    }

    // ---------------------------------------------------------------------
    // Deserialization: JSON string -> model
    // ---------------------------------------------------------------------

    @Benchmark
    fun kotlinxDeserialize(bh: Blackhole) {
        bh.consume(engines.kotlinxJson.decodeFromString(Feed.serializer(), json))
    }

    @Benchmark
    fun moshiReflectDeserialize(bh: Blackhole) {
        bh.consume(engines.moshiReflectAdapter.fromJson(json))
    }

    @Benchmark
    fun moshiCodegenDeserialize(bh: Blackhole) {
        bh.consume(engines.moshiCodegenAdapter.fromJson(json))
    }

    @Benchmark
    fun jacksonDeserialize(bh: Blackhole) {
        bh.consume(engines.jacksonMapper.readValue(json, PlainFeed::class.java))
    }

    @Benchmark
    fun jacksonBlackbirdDeserialize(bh: Blackhole) {
        bh.consume(engines.jacksonBlackbirdMapper.readValue(json, PlainFeed::class.java))
    }

    @Benchmark
    fun gsonDeserialize(bh: Blackhole) {
        bh.consume(engines.gson.fromJson(json, PlainFeed::class.java))
    }
}
