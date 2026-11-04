package com.veldtjumper.jvmjson

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.blackbird.BlackbirdModule
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import com.google.gson.Gson
import com.google.gson.GsonBuilder
import com.squareup.moshi.JsonAdapter
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import com.veldtjumper.jvmjson.model.CodegenFeed
import com.veldtjumper.jvmjson.model.PlainFeed
import kotlinx.serialization.json.Json

/**
 * Holds one configured engine per library. Keeping construction in one place makes
 * the benchmark methods small and ensures every library is set up the same way.
 */
class JsonEngines {
    val kotlinxJson: Json = Json { ignoreUnknownKeys = true }

    val moshiReflectAdapter: JsonAdapter<PlainFeed> =
        Moshi.Builder()
            .add(KotlinJsonAdapterFactory())
            .build()
            .adapter(PlainFeed::class.java)

    val moshiCodegenAdapter: JsonAdapter<CodegenFeed> =
        Moshi.Builder()
            .build()
            .adapter(CodegenFeed::class.java)

    val jacksonMapper: ObjectMapper = jacksonObjectMapper()

    val jacksonBlackbirdMapper: ObjectMapper =
        jacksonObjectMapper().registerModule(BlackbirdModule())

    val gson: Gson = GsonBuilder().create()
}
