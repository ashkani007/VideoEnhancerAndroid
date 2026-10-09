package com.vrvision.app.data

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Index
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase
import androidx.room.Update
import kotlinx.coroutines.flow.Flow

/** A video in the library: either an imported original or an enhanced output. */
@Entity(tableName = "videos", indices = [Index(value = ["uri"], unique = true), Index("sourceVideoId")])
data class VideoEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val uri: String,
    val displayName: String,
    val sizeBytes: Long?,
    val width: Int,
    val height: Int,
    val rotationDegrees: Int,
    val durationMs: Long,
    val frameRate: Float?,
    val videoMime: String?,
    val codecProfile: String?,
    val bitDepth: Int?,
    val bitrate: Long?,
    val hdr: Boolean?,
    val audioSummary: String,
    val audioTrackCount: Int,
    val subtitleTrackCount: Int,
    // User-confirmed interpretation (never changed silently).
    val layout: String,
    val packing: String,
    val projection: String,
    val swapEyes: Boolean,
    val formatConfirmed: Boolean,
    val formatHint: String,
    /** ORIGINAL or ENHANCED. */
    val kind: String = KIND_ORIGINAL,
    val sourceVideoId: Long? = null,
    /** For enhanced outputs: model, settings, timings and validation, as JSON. */
    val enhancementJson: String? = null,
    val addedAt: Long = System.currentTimeMillis(),
    val lastPositionMs: Long = 0,
) {
    companion object {
        const val KIND_ORIGINAL = "ORIGINAL"
        const val KIND_ENHANCED = "ENHANCED"
    }
}

@Entity(tableName = "calibrations")
data class CalibrationEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val name: String,
    val lensSeparationMm: Float,
    val lensToBottomMm: Float,
    val distortionEnabled: Boolean,
    val k1: Float,
    val k2: Float,
    val leftCenterOffsetX: Float,
    val leftCenterOffsetY: Float,
    val rightCenterOffsetX: Float,
    val rightCenterOffsetY: Float,
    val imageOffsetX: Float,
    val imageOffsetY: Float,
    val zoom: Float,
    val fovDegrees: Float,
    val viewportMargin: Float,
)

/** A preview or full enhancement job, local or cloud. */
@Entity(tableName = "jobs", indices = [Index("videoId")])
data class JobEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val videoId: Long,
    /** LOCAL_AI, LOCAL_CONVENTIONAL or CLOUD. */
    val mode: String,
    val isPreview: Boolean,
    /** QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED, UNSUPPORTED, AWAITING_CONSENT. */
    val status: String,
    val progress: Float = 0f,
    val stage: String = "",
    val message: String = "",
    val settingsJson: String,
    val previewStartMs: Long = 0,
    val previewDurationMs: Long = 0,
    val outputVideoId: Long? = null,
    val workId: String? = null,
    val cloudJobId: String? = null,
    val createdAt: Long = System.currentTimeMillis(),
    val startedAt: Long? = null,
    val finishedAt: Long? = null,
)

@Dao
interface VideoDao {
    @Query("SELECT * FROM videos WHERE kind = :kind ORDER BY addedAt DESC")
    fun observeByKind(kind: String): Flow<List<VideoEntity>>

    @Query("SELECT * FROM videos WHERE id = :id")
    fun observe(id: Long): Flow<VideoEntity?>

    @Query("SELECT * FROM videos WHERE id = :id")
    suspend fun get(id: Long): VideoEntity?

    @Query("SELECT * FROM videos WHERE uri = :uri")
    suspend fun findByUri(uri: String): VideoEntity?

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insert(v: VideoEntity): Long

    @Update
    suspend fun update(v: VideoEntity)

    @Query("UPDATE videos SET lastPositionMs = :pos WHERE id = :id")
    suspend fun savePosition(id: Long, pos: Long)

    @Query("DELETE FROM videos WHERE id = :id")
    suspend fun delete(id: Long)
}

@Dao
interface CalibrationDao {
    @Query("SELECT * FROM calibrations ORDER BY id")
    suspend fun all(): List<CalibrationEntity>

    @Query("SELECT * FROM calibrations ORDER BY id")
    fun observeAll(): Flow<List<CalibrationEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(c: CalibrationEntity): Long

    @Query("DELETE FROM calibrations WHERE id = :id")
    suspend fun delete(id: Long)
}

@Dao
interface JobDao {
    @Query("SELECT * FROM jobs ORDER BY createdAt DESC")
    fun observeAll(): Flow<List<JobEntity>>

    @Query("SELECT * FROM jobs WHERE id = :id")
    fun observe(id: Long): Flow<JobEntity?>

    @Query("SELECT * FROM jobs WHERE id = :id")
    suspend fun get(id: Long): JobEntity?

    @Query("SELECT * FROM jobs WHERE status IN ('QUEUED','RUNNING')")
    suspend fun active(): List<JobEntity>

    @Insert
    suspend fun insert(j: JobEntity): Long

    @Update
    suspend fun update(j: JobEntity)

    @Query("UPDATE jobs SET progress = :progress, stage = :stage WHERE id = :id")
    suspend fun progress(id: Long, progress: Float, stage: String)
}

@Database(entities = [VideoEntity::class, CalibrationEntity::class, JobEntity::class], version = 1, exportSchema = true)
abstract class AppDatabase : RoomDatabase() {
    abstract fun videos(): VideoDao
    abstract fun calibrations(): CalibrationDao
    abstract fun jobs(): JobDao
}
