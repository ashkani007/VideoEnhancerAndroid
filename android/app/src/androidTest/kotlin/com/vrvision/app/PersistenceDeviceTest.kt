package com.vrvision.app

import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.vrvision.app.data.AppDatabase
import com.vrvision.app.data.AppSettings
import com.vrvision.app.data.RoomCalibrationStore
import com.vrvision.core.calibration.HeadsetCalibration
import com.vrvision.core.calibration.ProfileManager
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith

/** Calibration profiles survive closing and reopening the Room database. */
@RunWith(AndroidJUnit4::class)
class PersistenceDeviceTest {

    @Test
    fun calibrationProfilesPersistAcrossDatabaseReopen(): Unit = runBlocking {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val name = "calibration-test.db"
        ctx.deleteDatabase(name)
        val settings = AppSettings(ctx)
        settings.activeCalibrationId = null

        var db = Room.databaseBuilder(ctx, AppDatabase::class.java, name).build()
        val pm = ProfileManager(RoomCalibrationStore(db.calibrations(), settings))
        pm.active()
        val saved = pm.createFrom(HeadsetCalibration(k1 = 0.31f, lensSeparationMm = 61f, rightCenterOffsetY = 0.02f), "Test headset")
        pm.select(saved.id)
        db.close()

        db = Room.databaseBuilder(ctx, AppDatabase::class.java, name).build()
        val reopened = ProfileManager(RoomCalibrationStore(db.calibrations(), settings)).active()
        assertEquals("Test headset", reopened.name)
        assertEquals(0.31f, reopened.k1, 1e-6f)
        assertEquals(61f, reopened.lensSeparationMm, 1e-6f)
        assertEquals(0.02f, reopened.rightCenterOffsetY, 1e-6f)
        db.close()
        ctx.deleteDatabase(name)
    }
}
