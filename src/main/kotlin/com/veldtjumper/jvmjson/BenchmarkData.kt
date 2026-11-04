package com.veldtjumper.jvmjson

import com.veldtjumper.jvmjson.model.Address
import com.veldtjumper.jvmjson.model.Feed
import com.veldtjumper.jvmjson.model.Geo
import com.veldtjumper.jvmjson.model.Post
import com.veldtjumper.jvmjson.model.User
import kotlinx.serialization.json.Json
import kotlin.math.roundToInt
import kotlin.random.Random

/**
 * Deterministic payload generator. The same seed and the same data are used for
 * every library, so the deserializers all receive byte-for-byte identical JSON.
 */
object BenchmarkData {
    val SIZES: List<Int> = listOf(10, 1_000, 25_000)

    private val canonicalJson = Json

    private val firstNames = listOf(
        "Ada", "Grace", "Linus", "Margaret", "Alan", "Barbara", "Ken", "Radia",
        "Guido", "Anita", "James", "Sophie", "Dennis", "Frances", "Bjarne",
        "Shafi", "Yukihiro", "Hedy", "Niklaus", "Carol",
    )

    private val lastNames = listOf(
        "Lovelace", "Hopper", "Torvalds", "Hamilton", "Turing", "Liskov",
        "Thompson", "Perlman", "van Rossum", "Borg", "Gosling", "Wilson",
        "Ritchie", "Allen", "Stroustrup", "Goldwasser", "Matsumoto", "Lamarr",
        "Wirth", "Shaw",
    )

    private val cities = listOf(
        "Austin", "Seattle", "Boston", "Chicago", "Denver", "Portland",
        "San Diego", "Nashville", "Raleigh", "Minneapolis",
    )

    private val streetNames = listOf(
        "Oak", "Maple", "Cedar", "Pine", "Elm", "Willow", "Birch", "Aspen",
        "Juniper", "Magnolia",
    )

    private val tags = listOf(
        "kotlin", "jvm", "json", "api", "backend", "mobile", "serialization",
        "performance", "openapi", "microservices",
    )

    private val postTitles = listOf(
        "Shipping faster with Kotlin",
        "A practical guide to JSON",
        "Notes from the benchmark lab",
        "Designing APIs that age well",
        "What we learned from profiling",
        "Small payloads, big wins",
        "The case for boring technology",
        "Reading the JIT tea leaves",
    )

    private val postBodies = listOf(
        "A short field note on measuring what actually matters, with reproducible numbers and a few sharp edges.",
        "Every abstraction has a cost. The useful question is whether the cost is visible where it matters most.",
        "We kept the workload realistic, pinned the toolchain, and let the harness do the arguing instead of intuition.",
        "Serialization is rarely the whole product, but it is often the quiet tax on every request and every screen.",
        "The interesting result was not the winner. It was how much the ranking changed once the payload got larger.",
        "Warmup, allocation, and escape analysis are doing more work than the annotations suggest. Measure carefully.",
    )

    fun feed(userCount: Int): Feed {
        require(userCount > 0) { "userCount must be positive" }
        val random = Random(0x5EED)
        val users = ArrayList<User>(userCount)

        repeat(userCount) { index ->
            val first = firstNames[index % firstNames.size]
            val last = lastNames[index % lastNames.size]
            val city = cities[(index * 3 + 1) % cities.size]
            val street = streetNames[(index * 5 + 2) % streetNames.size]
            val tagStart = index % tags.size
            val userTags = List(3) { offset -> tags[(tagStart + offset * 3) % tags.size] }
            val posts = List(3) { offset ->
                val postIndex = index * 3 + offset
                Post(
                    id = postIndex.toLong() + 1,
                    title = postTitles[postIndex % postTitles.size],
                    body = postBodies[postIndex % postBodies.size] + " Case " + (postIndex % 97) + ".",
                    likes = random.nextInt(0, 5_000),
                )
            }

            users += User(
                id = index.toLong() + 1,
                name = "$first $last",
                email = "${first.lowercase()}.${last.lowercase()}${index + 1}@example.com",
                active = index % 3 != 0,
                score = (random.nextDouble(0.0, 100.0) * 100).roundToInt() / 100.0,
                nickname = if (index % 4 == 0) null else "$first${random.nextInt(10, 99)}",
                tags = userTags,
                address = Address(
                    street = "${100 + random.nextInt(9_900)} $street St",
                    city = city,
                    zip = (10_000 + random.nextInt(90_000)).toString(),
                    geo = Geo(
                        lat = (random.nextDouble(-90.0, 90.0) * 1_000_000).roundToInt() / 1_000_000.0,
                        lng = (random.nextDouble(-180.0, 180.0) * 1_000_000).roundToInt() / 1_000_000.0,
                    ),
                ),
                posts = posts,
            )
        }

        return Feed(users)
    }

    fun canonicalJson(feed: Feed): String = canonicalJson.encodeToString(feed)
}
