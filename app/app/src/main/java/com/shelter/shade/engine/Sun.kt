package com.shelter.shade.engine

import kotlin.math.*

/**
 * Instantaneous solar position.
 *
 * @property azimuthDeg    Azimuth in degrees, north = 0, clockwise.
 * @property altitudeDeg   Elevation above horizon in degrees (negative when below horizon).
 * @property declinationDeg Solar declination in degrees.
 * @property isUp          True when the sun is above the horizon (altitude > 0).
 */
data class SolarPosition(
    val azimuthDeg: Double,
    val altitudeDeg: Double,
    val declinationDeg: Double,
    val isUp: Boolean,
)

// ---------------------------------------------------------------------------
// Atmospheric refraction correction
// ---------------------------------------------------------------------------

/**
 * Atmospheric refraction correction in degrees.
 *
 * Mirrors `_refraction_correction_deg` from sun.py (NOAA formula).
 */
private fun refractionCorrectionDeg(elevationDeg: Double): Double {
    if (elevationDeg > 85.0) return 0.0
    val te = tan(Math.toRadians(elevationDeg))
    val r: Double = when {
        elevationDeg > 5.0 ->
            58.1 / te - 0.07 / te.pow(3) + 0.000086 / te.pow(5)
        elevationDeg > -0.575 ->
            1735.0 + elevationDeg * (
                -518.2 + elevationDeg * (
                    103.4 + elevationDeg * (-12.79 + elevationDeg * 0.711)
                )
            )
        else ->
            -20.774 / te
    }
    return r / 3600.0
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Compute the solar position for a given location and instant using the NOAA
 * Solar Position Algorithm.
 *
 * Mirrors `solar_position` from sun.py exactly.
 *
 * @param lat              Geographic latitude in degrees (north positive).
 * @param lon              Geographic longitude in degrees (east positive).
 * @param epochMillis      UTC epoch in milliseconds (standard Java/Kotlin time).
 * @param applyRefraction  Whether to apply atmospheric refraction correction
 *                         (default true, same as Python default).
 * @return [SolarPosition] containing azimuth, altitude, declination, and isUp.
 */
fun solarPosition(
    lat: Double,
    lon: Double,
    epochMillis: Long,
    applyRefraction: Boolean = true,
): SolarPosition {

    // -----------------------------------------------------------------------
    // Julian Date from epoch millis (UTC)
    // -----------------------------------------------------------------------
    // Unix epoch (1970-01-01 00:00:00 UTC) = JD 2440587.5
    val jd = epochMillis / 86_400_000.0 + 2_440_587.5

    // Julian centuries from J2000.0
    val t = (jd - 2_451_545.0) / 36_525.0

    // -----------------------------------------------------------------------
    // Solar geometry
    // -----------------------------------------------------------------------

    // Geometric mean longitude of the Sun (degrees, mod 360)
    val l0 = (280.46646 + t * (36_000.76983 + 0.0003032 * t)).mod(360.0)

    // Mean anomaly of the Sun (degrees)
    val m = 357.52911 + t * (35_999.05029 - 0.0001537 * t)
    val mRad = Math.toRadians(m)

    // Eccentricity of Earth's orbit
    val e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)

    // Sun's equation of the centre
    val sinM = sin(mRad)
    val sin2M = sin(2.0 * mRad)
    val sin3M = sin(3.0 * mRad)
    val c = (sinM * (1.914602 - t * (0.004817 + 0.000014 * t))
            + sin2M * (0.019993 - 0.000101 * t)
            + sin3M * 0.000289)

    // Sun's true longitude (degrees)
    val trueLong = l0 + c

    // Apparent longitude (aberration + nutation)
    val omega = 125.04 - 1934.136 * t
    val appLong = trueLong - 0.00569 - 0.00478 * sin(Math.toRadians(omega))

    // Mean obliquity of the ecliptic (degrees)
    val eps0 = 23.0 + (26.0 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60.0) / 60.0
    // Corrected obliquity
    val eps = eps0 + 0.00256 * cos(Math.toRadians(omega))

    val epsRad = Math.toRadians(eps)
    val appLongRad = Math.toRadians(appLong)

    // Solar declination
    val declination = Math.toDegrees(asin(sin(epsRad) * sin(appLongRad)))

    // -----------------------------------------------------------------------
    // Equation of Time (minutes)
    // -----------------------------------------------------------------------
    val varY = tan(epsRad / 2.0).pow(2)
    val l0Rad = Math.toRadians(l0)
    val eot = 4.0 * Math.toDegrees(
        varY * sin(2.0 * l0Rad)
            - 2.0 * e * sinM
            + 4.0 * e * varY * sinM * cos(2.0 * l0Rad)
            - 0.5 * varY.pow(2) * sin(4.0 * l0Rad)
            - 1.25 * e.pow(2) * sin(2.0 * mRad)
    )

    // -----------------------------------------------------------------------
    // True Solar Time and Hour Angle
    // -----------------------------------------------------------------------
    // UTC minutes elapsed since midnight of the current day
    val utcMinutes = ((epochMillis % 86_400_000L) + 86_400_000L) % 86_400_000L / 60_000.0

    val trueSolarTime = (utcMinutes + eot + 4.0 * lon).mod(1440.0)
    var hourAngle = trueSolarTime / 4.0 - 180.0
    if (hourAngle < -180.0) hourAngle += 360.0

    // -----------------------------------------------------------------------
    // Zenith and elevation
    // -----------------------------------------------------------------------
    val latRad = Math.toRadians(lat)
    val declRad = Math.toRadians(declination)
    val haRad = Math.toRadians(hourAngle)

    var cosZenith = sin(latRad) * sin(declRad) + cos(latRad) * cos(declRad) * cos(haRad)
    cosZenith = cosZenith.coerceIn(-1.0, 1.0)
    val zenith = Math.toDegrees(acos(cosZenith))
    var elevation = 90.0 - zenith

    // -----------------------------------------------------------------------
    // Azimuth (north = 0, clockwise)
    // -----------------------------------------------------------------------
    val sinZenith = sin(Math.toRadians(zenith))
    val azimuth: Double = if (abs(sinZenith) < 1e-9) {
        // Sun is at zenith or nadir — azimuth undefined; use 0
        0.0
    } else {
        var cosAz = (sin(latRad) * cosZenith - sin(declRad)) / (cos(latRad) * sinZenith)
        cosAz = cosAz.coerceIn(-1.0, 1.0)
        val azCore = Math.toDegrees(acos(cosAz))
        if (hourAngle > 0.0) (azCore + 180.0) % 360.0 else (540.0 - azCore) % 360.0
    }

    // -----------------------------------------------------------------------
    // Atmospheric refraction correction
    // -----------------------------------------------------------------------
    if (applyRefraction) {
        elevation += refractionCorrectionDeg(elevation)
    }

    return SolarPosition(
        azimuthDeg = azimuth,
        altitudeDeg = elevation,
        declinationDeg = declination,
        isUp = elevation > 0.0,
    )
}
