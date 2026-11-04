import org.gradle.api.file.DuplicatesStrategy

plugins {
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.ksp)
    alias(libs.plugins.jmh)
}

group = "com.veldtjumper"
version = "1.0.0"

repositories {
    mavenCentral()
}

configurations.all {
    // Kotlin 2.x merged the JDK7/JDK8 extensions into kotlin-stdlib. Moshi and
    // Jackson still pull the old 1.8.x split artifacts transitively; keeping them
    // in the JMH fat jar can shadow the 2.4.x stdlib classes.
    exclude(group = "org.jetbrains.kotlin", module = "kotlin-stdlib-jdk7")
    exclude(group = "org.jetbrains.kotlin", module = "kotlin-stdlib-jdk8")
}

kotlin {
    jvmToolchain(21)
}

dependencies {
    implementation(libs.moshi)
    implementation(libs.moshi.kotlin)
    implementation(kotlin("reflect"))
    ksp(libs.moshi.codegen)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.jackson.databind)
    implementation(libs.jackson.module.kotlin)
    implementation(libs.jackson.module.blackbird)
    implementation(libs.gson)

    testImplementation(kotlin("test"))
    testImplementation(libs.junit.jupiter)
    testRuntimeOnly(libs.junit.platform.launcher)

    jmh(libs.jmh.core)
    jmh(libs.jmh.generator.annprocess)
}

fun gradleInt(name: String, fallback: Int): Int =
    providers.gradleProperty(name).orNull?.toInt() ?: fallback

jmh {
    jmhVersion = libs.versions.jmh.get()
    warmupIterations = gradleInt("jmh.warmupIterations", 5)
    iterations = gradleInt("jmh.iterations", 20)
    timeOnIteration = providers.gradleProperty("jmh.timeOnIteration").orNull ?: "1s"
    fork = gradleInt("jmh.fork", 1)
    resultFormat = "JSON"
    resultsFile = layout.buildDirectory.file("results/jmh/results.json").get().asFile
    humanOutputFile = layout.buildDirectory.file("results/jmh/human.txt").get().asFile
    jvmArgsAppend = listOf("-Xms3g", "-Xmx3g", "-XX:+AlwaysPreTouch")
    duplicateClassesStrategy = DuplicatesStrategy.WARN
}

tasks.test {
    useJUnitPlatform()
}

tasks.register<JavaExec>("payloadStats") {
    group = "benchmark"
    description = "Writes deterministic benchmark payloads and their size metadata."
    dependsOn(tasks.named("classes"))
    mainClass.set("com.veldtjumper.jvmjson.PayloadStatsKt")
    classpath = sourceSets["main"].runtimeClasspath
    args(layout.buildDirectory.dir("results/jmh").get().asFile.absolutePath)
}

tasks.named("jmh") {
    dependsOn(tasks.named("payloadStats"))
}
