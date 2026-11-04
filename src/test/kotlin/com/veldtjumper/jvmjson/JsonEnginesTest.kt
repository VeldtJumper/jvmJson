package com.veldtjumper.jvmjson

import com.veldtjumper.jvmjson.model.CodegenFeed
import com.veldtjumper.jvmjson.model.Feed
import com.veldtjumper.jvmjson.model.PlainFeed
import com.veldtjumper.jvmjson.model.toCodegen
import com.veldtjumper.jvmjson.model.toPlain
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull

class JsonEnginesTest {
    private val feed = BenchmarkData.feed(4)
    private val json = BenchmarkData.canonicalJson(feed)
    private val engines = JsonEngines()

    @Test
    fun `payload generation is deterministic`() {
        assertEquals(json, BenchmarkData.canonicalJson(BenchmarkData.feed(4)))
    }

    @Test
    fun `kotlinx serialization round trips`() {
        val decoded = engines.kotlinxJson.decodeFromString(Feed.serializer(), json)
        assertCanonical(decoded)

        val encoded = engines.kotlinxJson.encodeToString(Feed.serializer(), feed)
        assertCanonical(engines.kotlinxJson.decodeFromString(Feed.serializer(), encoded))
    }

    @Test
    fun `moshi reflection round trips`() {
        val decoded = engines.moshiReflectAdapter.fromJson(json)
        assertNotNull(decoded)
        assertPlain(decoded)

        val encoded = engines.moshiReflectAdapter.toJson(feed.toPlain())
        val roundTripped = engines.moshiReflectAdapter.fromJson(encoded)
        assertNotNull(roundTripped)
        assertPlain(roundTripped)
    }

    @Test
    fun `moshi codegen round trips`() {
        val decoded = engines.moshiCodegenAdapter.fromJson(json)
        assertNotNull(decoded)
        assertCodegen(decoded)

        val encoded = engines.moshiCodegenAdapter.toJson(feed.toCodegen())
        val roundTripped = engines.moshiCodegenAdapter.fromJson(encoded)
        assertNotNull(roundTripped)
        assertCodegen(roundTripped)
    }

    @Test
    fun `jackson round trips`() {
        val decoded = engines.jacksonMapper.readValue(json, PlainFeed::class.java)
        assertPlain(decoded)

        val encoded = engines.jacksonMapper.writeValueAsString(feed.toPlain())
        assertPlain(engines.jacksonMapper.readValue(encoded, PlainFeed::class.java))
    }

    @Test
    fun `jackson blackbird round trips`() {
        val decoded = engines.jacksonBlackbirdMapper.readValue(json, PlainFeed::class.java)
        assertPlain(decoded)

        val encoded = engines.jacksonBlackbirdMapper.writeValueAsString(feed.toPlain())
        assertPlain(engines.jacksonBlackbirdMapper.readValue(encoded, PlainFeed::class.java))
    }

    @Test
    fun `gson round trips`() {
        val decoded = engines.gson.fromJson(json, PlainFeed::class.java)
        assertPlain(decoded)

        val encoded = engines.gson.toJson(feed.toPlain())
        assertPlain(engines.gson.fromJson(encoded, PlainFeed::class.java))
    }

    private fun assertCanonical(value: Feed) {
        assertEquals(4, value.users.size)
        assertEquals(1L, value.users[0].id)
        assertEquals("Ada Lovelace", value.users[0].name)
        assertEquals("ada.lovelace1@example.com", value.users[0].email)
        assertNull(value.users[0].nickname)
        assertEquals(3, value.users[0].posts.size)
        assertEquals("Shipping faster with Kotlin", value.users[0].posts[0].title)
    }

    private fun assertPlain(value: PlainFeed) {
        assertEquals(4, value.users.size)
        assertEquals(1L, value.users[0].id)
        assertEquals("Ada Lovelace", value.users[0].name)
        assertEquals("ada.lovelace1@example.com", value.users[0].email)
        assertNull(value.users[0].nickname)
        assertEquals(3, value.users[0].posts.size)
        assertEquals("Shipping faster with Kotlin", value.users[0].posts[0].title)
    }

    private fun assertCodegen(value: CodegenFeed) {
        assertEquals(4, value.users.size)
        assertEquals(1L, value.users[0].id)
        assertEquals("Ada Lovelace", value.users[0].name)
        assertEquals("ada.lovelace1@example.com", value.users[0].email)
        assertNull(value.users[0].nickname)
        assertEquals(3, value.users[0].posts.size)
        assertEquals("Shipping faster with Kotlin", value.users[0].posts[0].title)
    }
}
