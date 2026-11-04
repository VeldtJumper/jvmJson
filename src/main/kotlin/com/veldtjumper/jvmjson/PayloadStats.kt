package com.veldtjumper.jvmjson

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.io.File
import java.security.MessageDigest
import java.time.Instant

@Serializable
private data class PayloadStat(
    val userCount: Int,
    val jsonBytes: Int,
    val sha256: String,
)

@Serializable
private data class RuntimeInfo(
    val javaVersion: String,
    val javaVendor: String,
    val osName: String,
    val osArch: String,
)

@Serializable
private data class PayloadStatsFile(
    val generatedAt: String,
    val runtime: RuntimeInfo,
    val sizes: List<PayloadStat>,
)

fun main(args: Array<String>) {
    val outputDir = File(args.firstOrNull() ?: "build/results/jmh")
    outputDir.mkdirs()

    val stats = BenchmarkData.SIZES.map { size ->
        val json = BenchmarkData.canonicalJson(BenchmarkData.feed(size))
        File(outputDir, "payload-$size.json").writeText(json)
        PayloadStat(
            userCount = size,
            jsonBytes = json.toByteArray(Charsets.UTF_8).size,
            sha256 = json.sha256(),
        )
    }

    val statsFile = PayloadStatsFile(
        generatedAt = Instant.now().toString(),
        runtime = RuntimeInfo(
            javaVersion = System.getProperty("java.version"),
            javaVendor = System.getProperty("java.vendor"),
            osName = System.getProperty("os.name"),
            osArch = System.getProperty("os.arch"),
        ),
        sizes = stats,
    )
    val prettyJson = Json { prettyPrint = true }
    val target = File(outputDir, "payload-stats.json")
    target.writeText(prettyJson.encodeToString(PayloadStatsFile.serializer(), statsFile))

    println("Wrote payload stats to ${target.absolutePath}")
    stats.forEach {
        println("  ${it.userCount} users: ${it.jsonBytes} bytes (${it.sha256.take(12)}...)")
    }
}

private fun String.sha256(): String {
    val digest = MessageDigest.getInstance("SHA-256").digest(toByteArray(Charsets.UTF_8))
    return digest.joinToString("") { "%02x".format(it) }
}
