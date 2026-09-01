import streamlit as st
import random
import requests
import base64
import os
import folium
from streamlit_folium import st_folium
from google.cloud import storage


BUCKET_NAME = "visual-geolocation-osv5m"
GCS_PREFIX = "data_for_front/raw_data"
LOCAL_IMAGES_DIR = "local_images"


def call_evaluate_api(guessed_lon, guessed_lat, challenge_id):
    url = "https://visual-geoloc-docker-766802765455.europe-west1.run.app/evaluate"
    params = {
        "guessed_longitude": guessed_lon,
        "guessed_latitude": guessed_lat,
        "challenge_id": challenge_id
    }
    response = requests.get(url, params=params)

    if response.status_code != 200:
        st.error(f"API Error ({response.status_code}): {response.text}")
        return None

    return response.json()


def get_image_base64(path):
    with open(path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()


@st.cache_data
def load_images_pool():
    """Download all images under GCS_PREFIX once, and build the images pool from them."""
    os.makedirs(LOCAL_IMAGES_DIR, exist_ok=True)

    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blobs = list(bucket.list_blobs(prefix=GCS_PREFIX))

    pool = []
    for blob in blobs:
        filename = blob.name.split("/")[-1]
        if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
            continue

        local_path = os.path.join(LOCAL_IMAGES_DIR, filename)
        if not os.path.exists(local_path):
            blob.download_to_filename(local_path)

        image_id = filename.rsplit(".", 1)[0]
        pool.append({"id": image_id, "path": local_path})

    return pool


st.set_page_config(layout="wide", page_title="Geoguesser 2.0-ish", page_icon="🌍")

st.markdown("""
    <style>
    h1 {
        text-align: center !important;
        font-size: 5rem !important;
        font-weight: 800 !important;
    }
    .subtitle-spaced {
        text-align: center;
        font-size: 1.6rem !important;
        margin-top: 1.5rem;
        margin-bottom: 2.5rem;
    }
    .stButton button {
        font-size: 1.3rem !important;
        padding: 0.75rem 1.5rem !important;
        border-radius: 50px !important;
    }
    .stButton button p {
        font-size: 1.3rem !important;
    }
    .stButton button[kind="primary"] {
        background-color: #B8086D !important;
        border-color: #B8086D !important;
    }
    div[data-testid="stCaptionContainer"] p {
        font-size: 1.1rem;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🌍 Geoguesser 2.0-ish")
st.markdown(
    '<p class="subtitle-spaced">Can you beat the machine at its own game?<br>Guess the location, then find out if you\'re smarter than a neural network 🧠</p>',
    unsafe_allow_html=True
)

IMAGES_POOL = load_images_pool()

MAP_HEIGHT = 500

if "current_challenge" not in st.session_state:
    st.session_state.current_challenge = random.choice(IMAGES_POOL)
    st.session_state.result = None
    st.session_state.guessed_lat = None
    st.session_state.guessed_lon = None

col1, col2 = st.columns(2)

with col1:
    st.subheader("📸 Where was this taken?")
    img_b64 = get_image_base64(st.session_state.current_challenge["path"])
    st.markdown(
        f'<img src="data:image/jpeg;base64,{img_b64}" '
        f'style="width:100%; height:{MAP_HEIGHT}px; object-fit:cover; border-radius:8px;">',
        unsafe_allow_html=True
    )

with col2:
    st.subheader("📍 Place your guess on the map")

    m = folium.Map(location=[20, 0], zoom_start=2)

    points = []

    if st.session_state.guessed_lat is not None:
        folium.Marker(
            [st.session_state.guessed_lat, st.session_state.guessed_lon],
            popup="Your guess",
            icon=folium.Icon(color="blue")
        ).add_to(m)
        points.append([st.session_state.guessed_lat, st.session_state.guessed_lon])

    if st.session_state.result:
        machine_data = st.session_state.result[1]
        true_data = st.session_state.result[2]

        folium.Marker(
            [machine_data["machine_lat"], machine_data["machine_lon"]],
            popup="Model's guess",
            icon=folium.Icon(color="red")
        ).add_to(m)
        points.append([machine_data["machine_lat"], machine_data["machine_lon"]])

        folium.Marker(
            [true_data["true_lat"], true_data["true_lon"]],
            popup="True location",
            icon=folium.Icon(color="green")
        ).add_to(m)
        points.append([true_data["true_lat"], true_data["true_lon"]])

    if len(points) >= 2:
        m.fit_bounds(points)

    map_data = st_folium(
        m,
        width=None,
        height=MAP_HEIGHT,
        returned_objects=["last_clicked"],
        key="main_map"
    )

    if map_data and map_data.get("last_clicked"):
        new_lat = map_data["last_clicked"]["lat"]
        new_lon = map_data["last_clicked"]["lng"]

        if new_lat != st.session_state.guessed_lat or new_lon != st.session_state.guessed_lon:
            st.session_state.guessed_lat = new_lat
            st.session_state.guessed_lon = new_lon
            st.rerun()

    if st.session_state.guessed_lat is not None:
        st.caption(f"Your guess: {st.session_state.guessed_lat:.4f}, {st.session_state.guessed_lon:.4f}")

btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 1])
with btn_col2:
    if st.button("🤓 Lock in my guess", type="primary", use_container_width=True) and st.session_state.guessed_lat is not None:
        with st.spinner("Crunching the numbers..."):
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
    machine_data = st.session_state.result[1]
    distance = human_data['human_haversine']
    machine_distance = machine_data['machine_haversine']

    st.divider()

    if distance < 100:
        st.success(f"🎉 Spot on! Only {distance:.0f} km off")
    elif distance < 1000:
        st.info(f"👍 Not bad! {distance:.0f} km off")
    else:
        st.warning(f"😅 {distance:.0f} km off — plenty of room to improve")

    if distance < machine_distance:
        st.success("🏆 You beat the machine this time!")
    else:
        st.info("🤖 The machine wins this round")

    score_col1, score_col2 = st.columns(2)
    with score_col1:
        st.metric("📍 Your distance", f"{distance:.0f} km")
        st.metric("⭐ Your score", f"{human_data['human_geoscore']:.2f}")
    with score_col2:
        st.metric("🤖 Model's distance", f"{machine_distance:.0f} km")
        st.metric("🎯 Model's score", f"{machine_data['machine_geoscore']:.2f}")

st.divider()

btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 1])
with btn_col2:
    if st.button("🔄 Let's give it another try", use_container_width=True):
        st.session_state.current_challenge = random.choice(IMAGES_POOL)
        st.session_state.result = None
        st.session_state.guessed_lat = None
        st.session_state.guessed_lon = None
        st.rerun()
