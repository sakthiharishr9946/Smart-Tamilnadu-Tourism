import streamlit as st
import folium
from folium.plugins import FastMarkerCluster, MarkerCluster
from streamlit_folium import st_folium

# Above this many points, markers are built in the browser from plain
# [lat, lon, label] data (FastMarkerCluster): ~10x less HTML and no
# per-marker Python work on every rerun.
FAST_CLUSTER_THRESHOLD = 150

_FAST_MARKER_CALLBACK = """
function (row) {
    var marker = L.marker(new L.LatLng(row[0], row[1]));
    marker.bindTooltip(row[2]);
    return marker;
}
"""

# CartoDB's named presets (folium's "CartoDB positron" / "dark_matter"
# shortcuts) now require an API key and return watermarked tiles without
# one. Esri's Canvas basemaps give the same light/dark look and stay free,
# key-less, anonymous tiles. "Street" is the standard OpenStreetMap map
# (roads, villages and temples labelled, in English and Tamil) and
# "Satellite" is Esri World Imagery - both free and key-less too.
MAP_TILES = {
    "Street": {
        "tiles": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "attr": '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    },
    "Satellite": {
        "tiles": (
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}"
        ),
        "attr": "Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics",
    },
    "Light": {
        "tiles": (
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            "Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
        ),
        "attr": "Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ",
    },
    "Dark": {
        "tiles": (
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            "Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
        ),
        "attr": "Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ",
    },
}


def render_map_view(places, zoom=7, key="map_view"):
    if not places:
        st.info("No location data available.")
        return

    map_points = []

    for place in places:
        latitude = place.get("latitude")
        longitude = place.get("longitude")

        if latitude is None or longitude is None:
            continue

        try:
            map_points.append(
                {
                    "latitude": float(latitude),
                    "longitude": float(longitude),
                    "name": place.get("place_name") or "Tourist place",
                    "category": place.get("category_name") or "",
                    "approximate": place.get("location_precision") == "locality",
                }
            )
        except (TypeError, ValueError):
            continue

    if not map_points:
        st.warning(
            "No valid coordinates are available "
            "for these destinations."
        )
        return

    theme_key = f"{key}_theme"
    theme = st.radio(
        "Map theme",
        options=list(MAP_TILES.keys()),
        index=list(MAP_TILES).index(st.session_state.get(theme_key, "Street"))
        if st.session_state.get(theme_key, "Street") in MAP_TILES else 0,
        horizontal=True,
        key=theme_key,
        label_visibility="collapsed",
    )

    center_lat = sum(point["latitude"] for point in map_points) / len(map_points)
    center_lon = sum(point["longitude"] for point in map_points) / len(map_points)

    fmap = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom,
        tiles=MAP_TILES[theme]["tiles"],
        attr=MAP_TILES[theme]["attr"],
    )

    if len(map_points) > 1:
        latitudes = [point["latitude"] for point in map_points]
        longitudes = [point["longitude"] for point in map_points]
        fmap.fit_bounds([[min(latitudes), min(longitudes)], [max(latitudes), max(longitudes)]], padding=(20, 20))

    for point in map_points:
        if point["approximate"]:
            point["name"] += " (approx. location)"

    if len(map_points) > FAST_CLUSTER_THRESHOLD:
        FastMarkerCluster(
            data=[
                [point["latitude"], point["longitude"],
                 point["name"] + (f" · {point['category']}" if point["category"] else "")]
                for point in map_points
            ],
            callback=_FAST_MARKER_CALLBACK,
        ).add_to(fmap)
        map_points = []
        cluster = fmap
    elif len(map_points) > 1:
        cluster = MarkerCluster().add_to(fmap)
    else:
        cluster = fmap

    marker_color = "orange" if theme == "Dark" else "red"

    for point in map_points:
        folium.Marker(
            location=[point["latitude"], point["longitude"]],
            tooltip=point["name"],
            popup=f"{point['name']}" + (f" · {point['category']}" if point["category"] else ""),
            icon=folium.Icon(color=marker_color, icon="map-marker", prefix="fa"),
        ).add_to(cluster)

    with st.container(border=True):
        st_folium(
            fmap,
            use_container_width=True,
            height=420,
            returned_objects=[],
            key=key,
        )
