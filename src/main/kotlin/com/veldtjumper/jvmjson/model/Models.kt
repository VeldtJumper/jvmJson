package com.veldtjumper.jvmjson.model

import com.squareup.moshi.JsonClass
import kotlinx.serialization.Serializable

/**
 * Canonical model used to build the payload and to drive kotlinx.serialization.
 * The plain and codegen models below deliberately mirror this shape so that each
 * library gets an idiomatic, statically known type to work with.
 */
@Serializable
data class Feed(
    val users: List<User>,
)

@Serializable
data class User(
    val id: Long,
    val name: String,
    val email: String,
    val active: Boolean,
    val score: Double,
    val nickname: String?,
    val tags: List<String>,
    val address: Address,
    val posts: List<Post>,
)

@Serializable
data class Address(
    val street: String,
    val city: String,
    val zip: String,
    val geo: Geo,
)

@Serializable
data class Geo(
    val lat: Double,
    val lng: Double,
)

@Serializable
data class Post(
    val id: Long,
    val title: String,
    val body: String,
    val likes: Int,
)

/** Plain Kotlin data classes used by Moshi reflection, Jackson, Blackbird and Gson. */
data class PlainFeed(
    val users: List<PlainUser>,
)

data class PlainUser(
    val id: Long,
    val name: String,
    val email: String,
    val active: Boolean,
    val score: Double,
    val nickname: String?,
    val tags: List<String>,
    val address: PlainAddress,
    val posts: List<PlainPost>,
)

data class PlainAddress(
    val street: String,
    val city: String,
    val zip: String,
    val geo: PlainGeo,
)

data class PlainGeo(
    val lat: Double,
    val lng: Double,
)

data class PlainPost(
    val id: Long,
    val title: String,
    val body: String,
    val likes: Int,
)

/** Separate model for Moshi codegen so the generated adapter is actually exercised. */
@JsonClass(generateAdapter = true)
data class CodegenFeed(
    val users: List<CodegenUser>,
)

@JsonClass(generateAdapter = true)
data class CodegenUser(
    val id: Long,
    val name: String,
    val email: String,
    val active: Boolean,
    val score: Double,
    val nickname: String?,
    val tags: List<String>,
    val address: CodegenAddress,
    val posts: List<CodegenPost>,
)

@JsonClass(generateAdapter = true)
data class CodegenAddress(
    val street: String,
    val city: String,
    val zip: String,
    val geo: CodegenGeo,
)

@JsonClass(generateAdapter = true)
data class CodegenGeo(
    val lat: Double,
    val lng: Double,
)

@JsonClass(generateAdapter = true)
data class CodegenPost(
    val id: Long,
    val title: String,
    val body: String,
    val likes: Int,
)

fun Feed.toPlain(): PlainFeed = PlainFeed(users.map { it.toPlain() })

private fun User.toPlain(): PlainUser = PlainUser(
    id = id,
    name = name,
    email = email,
    active = active,
    score = score,
    nickname = nickname,
    tags = tags,
    address = address.toPlain(),
    posts = posts.map { it.toPlain() },
)

private fun Address.toPlain(): PlainAddress = PlainAddress(
    street = street,
    city = city,
    zip = zip,
    geo = geo.toPlain(),
)

private fun Geo.toPlain(): PlainGeo = PlainGeo(lat = lat, lng = lng)

private fun Post.toPlain(): PlainPost = PlainPost(
    id = id,
    title = title,
    body = body,
    likes = likes,
)

fun Feed.toCodegen(): CodegenFeed = CodegenFeed(users.map { it.toCodegen() })

private fun User.toCodegen(): CodegenUser = CodegenUser(
    id = id,
    name = name,
    email = email,
    active = active,
    score = score,
    nickname = nickname,
    tags = tags,
    address = address.toCodegen(),
    posts = posts.map { it.toCodegen() },
)

private fun Address.toCodegen(): CodegenAddress = CodegenAddress(
    street = street,
    city = city,
    zip = zip,
    geo = geo.toCodegen(),
)

private fun Geo.toCodegen(): CodegenGeo = CodegenGeo(lat = lat, lng = lng)

private fun Post.toCodegen(): CodegenPost = CodegenPost(
    id = id,
    title = title,
    body = body,
    likes = likes,
)
