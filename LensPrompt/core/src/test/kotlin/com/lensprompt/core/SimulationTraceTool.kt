package com.lensprompt.core
import kotlin.test.Test

/**
 * Tuning aid: prints frame traces of a few scenarios.
 * Run with: LENSPROMPT_TRACE=1 ./gradlew :core:test --tests '*SimulationTraceTool*' -i
 */
class SimulationTraceTool {
    @Test fun dump() {
        if (System.getenv("LENSPROMPT_TRACE") == null) return
        val script = TestScripts.MACHINING
        fun run(name: String, s: SpeechScenario) {
            val f = SmartFollowSimulator(script).run(s.events(), s.durationMs + 3000)
            println("##### $name dur=${s.durationMs}")
            f.filter { it.timeMs % 1000 < 16 }.forEach {
                println("%6d %-14s match=%3d tgt=%6.2f disp=%6.2f conf=%.2f v=%.2f sv=%.0f".format(it.timeMs, it.state, it.matchedIndex, it.targetProgress, it.displayedProgress, it.confidence, it.readingVelocity, it.scrollVelocityPx))
            }
        }
        run("normal", SpeechScenario(script).read(0, 60, 2.5))
        run("pause", SpeechScenario(script).read(0, 30, 2.5).silence(5000).read(30, 50, 2.5))
        run("offscript", SpeechScenario(script).read(0, 30, 2.5).say("um so let me tell you a quick story about my weekend at the lake with friends", 2.8).read(30, 50, 2.5))
        run("skip", SpeechScenario(script).read(0, 33, 2.5).read(46, 80, 2.5))
    }
}
