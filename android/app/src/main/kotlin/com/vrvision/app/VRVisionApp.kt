package com.vrvision.app

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import androidx.room.Room
import com.vrvision.app.data.AppDatabase
import com.vrvision.app.data.AppSettings
import com.vrvision.app.data.RoomCalibrationStore
import com.vrvision.app.data.VideoRepository
import com.vrvision.app.device.DeviceInspector
import com.vrvision.app.enhance.JobManager
import com.vrvision.app.enhance.ModelRegistry
import com.vrvision.core.calibration.ProfileManager

/** Manual dependency container; the object graph is small enough not to need Hilt. */
class AppContainer(app: Application) {
    val database: AppDatabase = Room.databaseBuilder(app, AppDatabase::class.java, "vrvision.db").build()
    val settings = AppSettings(app)
    val videos = VideoRepository(app, database.videos())
    val profiles = ProfileManager(RoomCalibrationStore(database.calibrations(), settings))
    val device = DeviceInspector(app)
    val models = ModelRegistry(app)
    val jobs = JobManager(app, database.jobs(), settings)
    /** Enhancement choices being edited, keyed by video id (survives navigation, not process death). */
    val drafts = mutableMapOf<Long, com.vrvision.app.ui.screens.EnhanceDraft>()
}

class VRVisionApp : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_PROCESSING, getString(R.string.processing_channel), NotificationManager.IMPORTANCE_LOW),
        )
    }

    companion object {
        const val CHANNEL_PROCESSING = "processing"
    }
}
