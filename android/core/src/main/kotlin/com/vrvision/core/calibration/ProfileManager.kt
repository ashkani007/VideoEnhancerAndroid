package com.vrvision.core.calibration

/** Persistence port for calibration profiles; the app implements it with Room. */
interface CalibrationStore {
    suspend fun all(): List<HeadsetCalibration>
    /** Inserts when id == 0, otherwise updates. Returns the stored id. */
    suspend fun upsert(profile: HeadsetCalibration): Long
    suspend fun delete(id: Long)
    suspend fun activeId(): Long?
    suspend fun setActiveId(id: Long)
}

/**
 * Rules for multiple headset profiles: there is always at least one profile, exactly one
 * is active, names are unique, and every stored value is within safe limits.
 */
class ProfileManager(private val store: CalibrationStore) {

    suspend fun active(): HeadsetCalibration {
        val profiles = ensureDefault()
        val id = store.activeId()
        return profiles.firstOrNull { it.id == id } ?: profiles.first().also { store.setActiveId(it.id) }
    }

    suspend fun profiles(): List<HeadsetCalibration> = ensureDefault()

    suspend fun save(profile: HeadsetCalibration): HeadsetCalibration {
        val clean = profile.validated()
        val others = store.all().filter { it.id != clean.id }
        val name = uniqueName(clean.name, others.map { it.name }.toSet())
        val stored = clean.copy(name = name)
        val id = store.upsert(stored)
        return stored.copy(id = id)
    }

    suspend fun createFrom(base: HeadsetCalibration, name: String): HeadsetCalibration =
        save(base.copy(id = 0, name = name))

    suspend fun select(id: Long) {
        require(store.all().any { it.id == id }) { "No profile with id $id" }
        store.setActiveId(id)
    }

    /** Deletes a profile. The last profile cannot be deleted; deleting the active one activates another. */
    suspend fun delete(id: Long): Boolean {
        val all = store.all()
        if (all.size <= 1 || all.none { it.id == id }) return false
        val wasActive = store.activeId() == id
        store.delete(id)
        if (wasActive) store.setActiveId(store.all().first().id)
        return true
    }

    suspend fun importJson(json: String): HeadsetCalibration =
        save(CalibrationCodec.decode(json).copy(id = 0))

    private suspend fun ensureDefault(): List<HeadsetCalibration> {
        val all = store.all()
        if (all.isNotEmpty()) return all
        val id = store.upsert(HeadsetCalibration())
        store.setActiveId(id)
        return store.all()
    }

    private fun uniqueName(base: String, taken: Set<String>): String {
        if (base !in taken) return base
        var i = 2
        while ("$base ($i)" in taken) i++
        return "$base ($i)".take(HeadsetCalibration.MAX_NAME + 6)
    }
}
