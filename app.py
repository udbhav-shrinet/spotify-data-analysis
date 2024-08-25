from flask import Flask, request, render_template
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

app = Flask(__name__)

# Set up Spotify API credentials
client_id = "3035bc212e2a4dd4b160bc6d1e2fe7dc"
client_secret = "cdc8bf85ae114b53912cdfc947355561"
client_credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

def get_track_features(track_id):
    features = sp.audio_features(track_id)[0]
    return {
        'Danceability': features['danceability'],
        'Energy': features['energy'],
        'Key': features['key'],
        'Loudness': features['loudness'],
        'Speechiness': features['speechiness'],
        'Mode': 'Major' if features['mode'] == 1 else 'Minor',
        'Acousticness': features['acousticness'],
        'Instrumentalness': features['instrumentalness'],
        'Liveness': features['liveness'],
        'Valence': features['valence'],
        'Tempo': features['tempo']
    }

# Define genre groups
genre_groups = {
    'Pop music': ['pop', 'bedroom pop', 'australian pop'],
    'Hip hop music': ['hip hop', 'rap', 'trap'],
    'Rock music': ['rock', 'alternative rock', 'indie rock'],
    'Rhythm and blues': ['r&b', 'soul'],
    'Soul music': ['soul'],
    'Reggae': ['reggae', 'dancehall'],
    'Country': ['country', 'folk'],
    'Funk': ['funk'],
    'Folk music': ['folk'],
    'Middle Eastern music': ['middle eastern'],
    'Jazz': ['jazz', 'smooth jazz'],
    'Disco': ['disco'],
    'Classical music': ['classical'],
    'Electronic music': ['electronic', 'dance', 'edm'],
    'Music of Latin America': ['latin', 'salsa', 'tango'],
    'Blues': ['blues'],
    'Music for children': ['children'],
    'New-age music': ['new-age'],
    'Vocal music': ['vocal'],
    'Music of Africa': ['africa'],
    'Christian music': ['christian'],
    'Music of Asia': ['asian'],
    'Ska': ['ska'],
    'Traditional music': ['traditional'],
    'Independent music': ['indie']
}

def map_genre(genre):
    for group, genres in genre_groups.items():
        if genre.lower() in genres:
            return group
    return 'Other'  # Default category for genres not listed

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    playlist_url = request.form['playlist_url']
    playlist_id = playlist_url.split('/')[-1].split('?')[0]

    # Get playlist details
    playlist = sp.playlist(playlist_id)
    tracks = playlist['tracks']['items']

    # Prepare data for DataFrame
    data = []
    for item in tracks:
        track = item['track']
        track_id = track['id']
        track_name = track['name']
        album_name = track['album']['name']
        album_release_date = track['album']['release_date']
        track_popularity = track['popularity']
        track_duration_ms = track['duration_ms']
        artist_ids = [artist['id'] for artist in track['artists']]
        artist_names = [artist['name'] for artist in track['artists']]
        genres = ', '.join(sp.artist(artist_ids[0])['genres'])
        
        # Get artist followers (for the first artist)
        artist_followers = sp.artist(artist_ids[0])['followers']['total']
        
        features = get_track_features(track_id)
        album_image_url = track['album']['images'][0]['url']  # Get the URL of the album cover
        
        data.append({
            'Name': track_name,
            'Album': album_name,
            'Release Date': album_release_date,
            'Popularity': track_popularity,
            'Duration (ms)': track_duration_ms,
            'Artist': ', '.join(artist_names),
            'Genres': genres,
            'Artist Followers': artist_followers,
            **features,
            'Album Image URL': album_image_url  # Add the album image URL
        })

    # Create a DataFrame
    df = pd.DataFrame(data)

    # Convert Release Date to datetime, handling various formats
    def parse_release_date(date_str):
        try:
            return pd.to_datetime(date_str, format='%Y-%m-%d', errors='coerce')
        except ValueError:
            return pd.to_datetime(date_str, format='%Y', errors='coerce')

    df['Release Date'] = df['Release Date'].apply(parse_release_date)

    # Convert duration from milliseconds to minutes
    df['Duration (min)'] = df['Duration (ms)'] / 60000

    # Map genres to broader categories and prepare for sunburst chart
    genre_data = []
    for index, row in df.iterrows():
        broad_genres = list(set(map(map_genre, row['Genres'].split(', '))))
        for genre in broad_genres:
            genre_data.append({
                'Parent': 'All Genres' if len(broad_genres) == 1 else ', '.join(broad_genres),
                'Label': genre,
                'Value': 1
            })

    # Create a DataFrame for the sunburst chart
    genre_df = pd.DataFrame(genre_data)

    # Genre Distribution (Sunburst Chart)
    fig_genres = px.sunburst(
        genre_df,
        path=['Parent', 'Label'],
        values='Value',
        title="Genre Distribution"
    )

    # Track Features Radar Chart (All tracks)
    radar_categories = ['Danceability', 'Energy', 'Acousticness', 'Instrumentalness', 'Liveness', 'Valence']
    fig_radar = go.Figure()
    for index, row in df.iterrows():
        fig_radar.add_trace(go.Scatterpolar(
            r=[row[cat] for cat in radar_categories],
            theta=radar_categories,
            fill='toself',
            name=row['Name']
        ))
    fig_radar.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1]
            )),
        title="Track Features Radar Chart"
    )

    # Generate other visualizations
    fig_dance_energy = px.scatter(df, x='Danceability', y='Energy', hover_name='Name', title="Danceability vs. Energy")
    fig_popularity = px.line(df.sort_values('Release Date'), x='Release Date', y='Popularity', title="Track Popularity Over Time")
    fig_durations = px.histogram(df, x='Duration (min)', nbins=20, title="Track Duration Distribution")
    fig_artist_popularity = px.bar(df, x='Artist', y='Artist Followers', title="Artist Popularity")
    fig_loudness_valence = px.scatter(df, x='Loudness', y='Valence', hover_name='Name', title="Loudness vs. Valence")

    # Combine all charts into one HTML
    charts = {
        'Table': df[['Name', 'Album', 'Artist']].head(7).to_html(classes='table table-striped', index=False),
        'Genre Distribution': fig_genres.to_html(full_html=False),
        'Track Features Radar Chart': fig_radar.to_html(full_html=False),
        'Danceability vs. Energy': fig_dance_energy.to_html(full_html=False),
        'Track Popularity Over Time': fig_popularity.to_html(full_html=False),
        'Track Duration Distribution': fig_durations.to_html(full_html=False),
        'Artist Popularity': fig_artist_popularity.to_html(full_html=False),
        'Loudness vs. Valence': fig_loudness_valence.to_html(full_html=False),
    }

    return render_template('result.html', charts=charts)

if __name__ == '__main__':
    app.run(debug=True)
