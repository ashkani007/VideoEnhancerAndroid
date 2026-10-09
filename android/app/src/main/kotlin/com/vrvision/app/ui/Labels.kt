package com.vrvision.app.ui.screens

import com.vrvision.core.projection.ProjectionType
import com.vrvision.core.stereo.StereoLayout
import com.vrvision.core.stereo.StereoPacking

fun ProjectionType.label(): String = when (this) {
    ProjectionType.FLAT -> "Flat 2D screen"
    ProjectionType.EQUIRECT_180 -> "VR180"
    ProjectionType.EQUIRECT_360 -> "VR360"
}

fun StereoLayout.label(): String = when (this) {
    StereoLayout.MONO -> "Mono"
    StereoLayout.SIDE_BY_SIDE -> "Side-by-side 3D"
    StereoLayout.TOP_BOTTOM -> "Top-bottom 3D"
}

fun StereoPacking.label(): String = when (this) {
    StereoPacking.FULL -> "Full"
    StereoPacking.HALF -> "Half (squeezed)"
}
