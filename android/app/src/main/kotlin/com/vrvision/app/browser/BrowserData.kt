package com.vrvision.app.browser

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

/*
 * Browser data lives in its own database (browser.db) so it never touches the video library and
 * can be wiped by "Clear browsing data" without risk. It is excluded from backups like all app
 * data (res/xml/data_extraction_rules.xml). No cookies, form data or credentials are stored here.
 */

@Entity(tableName = "bookmarks", indices = [Index(value = ["url"], unique = true)])
data class BookmarkEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val url: String,
    val title: String,
    val createdAt: Long = System.currentTimeMillis(),
)

@Entity(tableName = "history", indices = [Index("visitedAt")])
data class HistoryEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val url: String,
    val title: String,
    val visitedAt: Long = System.currentTimeMillis(),
)

/** Open tabs for session restore: URL and title only. */
@Entity(tableName = "session_tabs")
data class SessionTabEntity(
    @PrimaryKey val id: Long,
    val url: String,
    val title: String,
    val position: Int,
    val active: Boolean,
)

@Entity(tableName = "downloads")
data class DownloadEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    /** android.app.DownloadManager id. */
    val systemId: Long,
    val url: String,
    val fileName: String,
    val mimeType: String?,
    val category: String,
    /** PENDING, RUNNING, SUCCESSFUL, FAILED, CANCELLED. */
    val status: String = "PENDING",
    val bytesDone: Long = 0,
    val bytesTotal: Long = -1,
    val localPath: String? = null,
    val failure: String? = null,
    /** NONE, PLAY or ENHANCE: what the user wanted to do with this file when it completes. */
    val purpose: String = "NONE",
    val layout: String? = null,
    val projection: String? = null,
    val importedVideoId: Long? = null,
    val createdAt: Long = System.currentTimeMillis(),
)

@Dao
interface BrowserDao {
    @Query("SELECT * FROM bookmarks ORDER BY createdAt DESC")
    fun bookmarks(): Flow<List<BookmarkEntity>>

    @Query("SELECT COUNT(*) FROM bookmarks WHERE url = :url")
    fun isBookmarked(url: String): Flow<Int>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun addBookmark(b: BookmarkEntity): Long

    @Query("DELETE FROM bookmarks WHERE url = :url")
    suspend fun removeBookmark(url: String)

    @Query("SELECT * FROM history ORDER BY visitedAt DESC LIMIT 500")
    fun history(): Flow<List<HistoryEntity>>

    @Insert
    suspend fun addHistory(h: HistoryEntity): Long

    @Query("SELECT * FROM history ORDER BY visitedAt DESC LIMIT 1")
    suspend fun lastHistory(): HistoryEntity?

    @Query("DELETE FROM history WHERE id NOT IN (SELECT id FROM history ORDER BY visitedAt DESC LIMIT 2000)")
    suspend fun trimHistory()

    @Query("DELETE FROM history")
    suspend fun clearHistory()

    @Query("SELECT * FROM session_tabs ORDER BY position")
    suspend fun sessionTabs(): List<SessionTabEntity>

    @Query("DELETE FROM session_tabs")
    suspend fun clearSession()

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun saveSession(tabs: List<SessionTabEntity>)

    @Query("SELECT * FROM downloads ORDER BY createdAt DESC")
    fun downloads(): Flow<List<DownloadEntity>>

    @Query("SELECT * FROM downloads WHERE status IN ('PENDING','RUNNING')")
    suspend fun activeDownloads(): List<DownloadEntity>

    @Query("SELECT * FROM downloads")
    suspend fun allDownloads(): List<DownloadEntity>

    @Query("SELECT * FROM downloads WHERE id = :id")
    suspend fun download(id: Long): DownloadEntity?

    @Insert
    suspend fun addDownload(d: DownloadEntity): Long

    @Update
    suspend fun updateDownload(d: DownloadEntity)

    @Query("DELETE FROM downloads")
    suspend fun clearDownloads()
}

@Database(
    entities = [BookmarkEntity::class, HistoryEntity::class, SessionTabEntity::class, DownloadEntity::class],
    version = 1,
    exportSchema = true,
)
abstract class BrowserDatabase : RoomDatabase() {
    abstract fun dao(): BrowserDao
}
