import streamlit as st
import random
import requests
import folium
from streamlit_folium import st_folium


def call_evaluate_api(guessed_lon, guessed_lat, challenge_id):
    url = "https://visual-geoloc-docker-766802765455.europe-west1.run.app/evaluate"
    params = {
        "guessed_longitude": guessed_lon,
        "guessed_latitude": guessed_lat,
        "challenge_id": challenge_id
    }
    response = requests.get(url, params=params)

    if response.status_code != 200:
        st.error(f"Erreur API ({response.status_code}) : {response.text}")
        return None

    return response.json()


st.set_page_config(layout="wide")
st.title("🌍 Geoguesser 2.0-ish")

DISPLAY_WIDTH = 700

IMAGES_POOL = [
    {"id": "101724", "path": "/home/sabrina/code/sabrina-hash4/475980663820534.jpg"},
]

if "current_challenge" not in st.session_state:
    st.session_state.current_challenge = random.choice(IMAGES_POOL)
    st.session_state.result = None
    st.session_state.guessed_lat = None
    st.session_state.guessed_lon = None

st.image(st.session_state.current_challenge["path"], width=DISPLAY_WIDTH)

st.subheader("Placez votre guess sur la carte (cliquez pour choisir un point)")

m = folium.Map(location=[20, 0], zoom_start=2)

if st.session_state.guessed_lat is not None:
    folium.Marker(
        [st.session_state.guessed_lat, st.session_state.guessed_lon],
        popup="Votre guess",
        icon=folium.Icon(color="blue")
    ).add_to(m)

if st.session_state.result:
    true_data = st.session_state.result[1]
    folium.Marker(
        [true_data["true_lat"], true_data["true_lon"]],
        popup="Vraie position",
        icon=folium.Icon(color="green")
    ).add_to(m)

map_data = st_folium(
    m,
    width=DISPLAY_WIDTH,
    height=500,
    returned_objects=["last_clicked"],
    key="main_map"
)

if map_data and map_data.get("last_clicked"):
    st.session_state.guessed_lat = map_data["last_clicked"]["lat"]
    st.session_state.guessed_lon = map_data["last_clicked"]["lng"]

if st.session_state.guessed_lat is not None:
    st.write(f"Votre guess : {st.session_state.guessed_lat:.4f}, {st.session_state.guessed_lon:.4f}")

if st.button("Valider mon guess") and st.session_state.guessed_lat is not None:
    result = call_evaluate_api(
        guessed_lon=st.session_state.guessed_lon,
        guessed_lat=st.session_state.guessed_lat,
        challenge_id=st.session_state.current_challenge["id"]
    )
    if result is not None:
        st.session_state.result = result
        st.rerun()

if st.session_state.result:
    human_data = st.session_state.result[0]
    st.metric("Distance", f"{human_data['human_haversine']:.0f} km")
    st.metric("Score", f"{human_data['human_geoscore']:.3f}")

if st.button("🔄 Nouvelle image"):
    st.session_state.current_challenge = random.choice(IMAGES_POOL)
    st.session_state.result = None
    st.session_state.guessed_lat = None
    st.session_state.guessed_lon = None
    st.rerun()
