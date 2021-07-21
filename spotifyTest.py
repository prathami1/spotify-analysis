import lyrics_getter
from pprint import pprint
import time
import sys
import os
import shutil
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import datetime
import random
import math

import sentiment_analysis

def init_spotify():
    scope = "user-read-currently-playing user-read-recently-played playlist-read-private playlist-read-collaborative"

    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))

    return sp

def create_vector_values(sp,txt):
    song_list, artist_list = None, None
    with open("reference_songs/" + txt + ".txt", "r") as f:
        lines = f.readlines()
        song_list = [x.strip() for x in lines[0::2]]
        artist_list = [x.strip() for x in lines[1::2]]
    track_ids = []
    for index in range(len(song_list)):
        track, artist = song_list[index], artist_list[index]

        track_id = sp.search(q='track:' + track, limit=1,type='track')
        track_id = track_id['tracks']['items'][0]['id']
        track_ids.append(track_id)
    main_frame = pd.DataFrame()
    main_frame['Song ID'] = track_ids
    final_audio_features = []
    all_song_ids = main_frame['Song ID']
    num_songids = len(all_song_ids)
    # print("song ids:" + str(num_songids))
    TRACK_REQUEST_LIMIT = 100
    for index in range(0, num_songids, TRACK_REQUEST_LIMIT):
        print(index)
        curr_songids = all_song_ids[index:min(num_songids, index + TRACK_REQUEST_LIMIT)]
        features = sp.audio_features(curr_songids)
        final_audio_features += features

    danceabilities = [features['danceability'] for features in final_audio_features]
    energies = [features['energy'] for features in final_audio_features]
    tempos = [features['tempo'] for features in final_audio_features]
    valences = [features['valence'] for features in final_audio_features]

    print(len(all_tracks))
    print(len(danceabilities))

    main_frame['Danceability'] = danceabilities
    main_frame['Energy'] = energies
    main_frame['Tempo'] = tempos
    main_frame['Valence'] = valences
    d = {'Danceability': main_frame['Danceability'].mean(),'Energy': main_frame['Energy'].mean(), 'Tempo': main_frame['Tempo'].mean(),'Valence': main_frame['Valence'].mean()}
    return d

def classify_song_emotion(song_values):
    def error(v1, v2, avg_tempo):
        temp = 0
        for i in range(len(v1)):
            if i == 2:
                currV1 = v1[i]/avg_tempo
                currV2 = v2[i]/avg_tempo
            else:
                currV1 = v1[i]
                currV2 = v2[i]
            temp += abs((currV1 - currV2))**2
        return math.sqrt(temp)

    classifier_dict = {"Happy": (0.6575, 0.6685, 124.95204999999999, 0.6319), "Sad": (0.52105, 0.43390000000000006, 111.12160000000002, 0.27843999999999997), "Hype": (0.601590909090909, 0.7075454545454546, 128.5876363636363, 0.44953181818181825)}
    avg_tempo = sum([i[2] for key, i in classifier_dict.items()]) / len(classifier_dict)
    best_error = float('inf')
    best_emotion = None
    for key, value in classifier_dict.items():
        if error(value, song_values, avg_tempo) < best_error:
            best_error = error(value, song_values, avg_tempo)
            best_emotion = key
    return best_emotion


def get_tracks_from_raw(sp, data):
    TRACK_REQUEST_LIMIT = 100
    final_data_frame = None
    data_for_dataframe = []
    for p in data['items']:
        if p['track'] is None:
            print("[BAD]")
            continue
        song_title = p['track']['name']
        artist_name = p['track']['artists'][0]['name']

        played_at = p['played_at']
        id = p['track']['id']
        data_for_dataframe.append([song_title, artist_name, played_at,id])

    main_frame =pd.DataFrame(data_for_dataframe, columns = ['Name', 'Artist', 'Time', 'Song ID'])

    final_audio_features = []
    all_song_ids = main_frame['Song ID']
    num_songids = len(all_song_ids)
    print("song ids:" + str(num_songids))
    for index in range(0, num_songids, TRACK_REQUEST_LIMIT):
        print(index)
        curr_songids = all_song_ids[index:min(num_songids, index + TRACK_REQUEST_LIMIT)]
        features = sp.audio_features(curr_songids)
        final_audio_features += features

    danceabilities = [features['danceability'] for features in final_audio_features]
    energies = [features['energy'] for features in final_audio_features]
    tempos = [features['tempo'] for features in final_audio_features]
    valences = [features['valence'] for features in final_audio_features]

    print(len(all_tracks))
    print(len(danceabilities))

    main_frame['Danceability'] = danceabilities
    main_frame['Energy'] = energies
    main_frame['Tempo'] = tempos
    main_frame['Valence'] = valences


    return main_frame

def get_sentiment_from_song(title, artist):
    lyrics = lyrics_getter.get_song_lyrics(title, artist)
    if lyrics is None:
        return None
    analysis = sentiment_analysis.analyze_text_sentiment(lyrics)

    sign = 1
    if (math.random()) > 0.5:
        sign = -1
    analysis = {'score' : math.random() * sign, 'magnitude' : math.random()}

    return analysis['score'] * analysis['magnitude']


def calculate_emotion(sentiment, danceability, energy, tempo, valence):
    return (sentiment * 2) + (danceability * 3) + (energy * 3) + (tempo / 100) + (valence * 3)


def get_emotion_value_from_song(title, artist, danceability=0, energy=0, tempo=0, valence=0):
    sentiment = get_sentiment_from_song(title, artist)
    if sentiment is None:
        sentiment = 0
    return calculate_emotion(sentiment, danceability, energy, tempo, valence)

callSentimentAnalysis = False
maxSentimentCalls = 10
sentimentCalls = 0
def get_emotion_value_from_playlist(zipped=None, danceability=0, energy=0, tempo=0, valence=0):
    global callSentimentAnalysis
    global sentimentCalls
    global maxSentimentCalls
    analysis = None
    if zipped is not None and callSentimentAnalysis and sentimentCalls < maxSentimentCalls:
        sentimentCalls += 1

        MAX_SAMPLE_LEN = 6
        MAX_BATCH_LEN = 3
        sampled_zipped = random.sample(zipped, min(MAX_SAMPLE_LEN, len(zipped)))
        print("Getting lyrics")
        sampled_lyrics = lyrics_getter.get_song_lyrics_batch(sampled_zipped)
        sampled_lyrics = [l[1] for l in sampled_lyrics]
        batched_lyrics = [". ".join(sampled_lyrics[i:i+MAX_BATCH_LEN]) for i in range (0, len(sampled_lyrics), MAX_BATCH_LEN)]

        print("analyzing sentiment")
        analyses = sentiment_analysis.analyze_text_sentiment_batch(batched_lyrics)
        if len(analyses) == 0:
            analysis = {'score': 0, 'magnitude': 0}
        else:
            analysis = {'score' : sum(res['score'] for res in analyses) / len(analyses),
                    'magnitude' :  sum(res['magnitude'] for res in analyses) / len(analyses)}
    else:
        sign = 1
        if (random.random()) > 0.5:
            sign = -1
        analysis = {'score' : random.random() * sign, 'magnitude' : random.random()}

    sentiment = analysis['score'] * analysis['magnitude']

    return calculate_emotion(sentiment, danceability, energy, tempo, valence)

def get_average_values_from_playlist(dataframe, zipped=None):
    res = {}
    avg_danceability = dataframe['Danceability'].mean()
    avg_energy = dataframe['Energy'].mean()
    avg_tempo = dataframe['Tempo'].mean()
    avg_valence = dataframe['Valence'].mean()
    avg_emotion = get_emotion_value_from_playlist(zipped, avg_danceability, avg_energy, avg_tempo, avg_valence)

    res['Danceability'] = avg_danceability
    res['Energy'] = avg_energy
    res['Tempo'] = avg_tempo
    res['Valence'] = avg_valence
    res['Emotion Score'] = avg_emotion

    return res

def get_playlist_tracks_from_raw(data, sp):
    final_data_frame = None
    data_for_dataframe = []
    for p in data['items']:
        if p['track'] is None:
            continue
        song_title = p['track']['name']
        artist_name = p['track']['artists'][0]['name']
        song_id = p['track']['id']
        if not song_id:
            continue
        song_analysis = sp.audio_features([song_id])
        if not song_analysis:
            continue
        danceability = song_analysis[0]['danceability']
        energy = song_analysis[0]['energy']
        tempo = song_analysis[0]['tempo']
        valence = song_analysis[0]['valence']
        emotion_score = get_emotion_value_from_song(song_title, artist_name, danceability, energy, tempo, valence)
        data_for_dataframe.append([song_title, artist_name, song_id])
    return pd.DataFrame(data_for_dataframe, columns = ['Name', 'Artist', 'Song ID'])

def get_playlist_tracks(sp, id, num_tracks):
    TRACK_REQUEST_LIMIT = 100

    all_tracks = None
    playlist_tracks = None
    for index in range(0, num_tracks, TRACK_REQUEST_LIMIT):
        playlist_track_data = sp.playlist_tracks(id, limit=TRACK_REQUEST_LIMIT, offset=index)
        playlist_tracks = get_playlist_tracks_from_raw(playlist_track_data, sp)
        if all_tracks is None:
            all_tracks = playlist_tracks
        else:
            all_tracks = all_tracks.append(playlist_tracks, ignore_index=True)

    final_audio_features = []
    all_song_ids = all_tracks['Song ID']
    num_songids = len(all_song_ids)
    print("song ids:" + str(num_songids))
    for index in range(0, num_songids, TRACK_REQUEST_LIMIT):
        print(index)
        curr_songids = all_song_ids[index:min(num_songids, index + TRACK_REQUEST_LIMIT)]
        features = sp.audio_features(curr_songids)
        final_audio_features += features

    danceabilities = [features['danceability'] for features in final_audio_features]
    energies = [features['energy'] for features in final_audio_features]
    tempos = [features['tempo'] for features in final_audio_features]
    valences = [features['valence'] for features in final_audio_features]

    print(len(all_tracks))
    print(len(danceabilities))

    all_tracks['Danceability'] = danceabilities
    all_tracks['Energy'] = energies
    all_tracks['Tempo'] = tempos
    all_tracks['Valence'] = valences


    return all_tracks

'''
Returns an array of tuples (playlist_name, playlist_id, playlist_track_count)
'''
def get_current_user_playlists(sp):
    playlist_data = sp.current_user_playlists()

    playlists = []
    for p in playlist_data['items']:
        playlists += [(p['name'], p['id'], p['tracks']['total'])]

    return playlists


def get_current_user_recently_played(sp):
    recently_played_data = sp.current_user_recently_played(limit=50)

    recently_played = get_tracks_from_raw(sp, recently_played_data)

    return recently_played

def analyze_user_recently_played(sp):
    tracks_dataframe = get_current_user_recently_played(sp)
    curr_avg_vals = get_average_values_from_playlist(tracks_dataframe)
    curr_emotion = classify_song_emotion((curr_avg_vals['Danceability'],
                                              curr_avg_vals['Energy'],
                                              curr_avg_vals['Tempo'],
                                              curr_avg_vals['Valence']))
    curr_dict = {'averages' : curr_avg_vals, 'emotion' : curr_emotion}
    return curr_dict

def get_playlist_lyrics(sp, name, id, num_tracks):
    playlist_lyrics = []
    print(name)
    tracks = get_playlist_tracks(sp, id, num_tracks)
    print("[FOUND SONGS]", len(tracks), "songs")

    for index, track_item in tracks.iterrows():
        print(track_item)
        song_title, artist_name = track_item["Name"], track_item["Artist"]
        lyrics = lyrics_getter.get_song_lyrics(song_title, artist_name)
        if lyrics is not None:
            playlist_lyrics += [(song_title, artist_name, lyrics)]

            folder_name = "lyrics/" + name + "/"
            title = ''.join(ch for ch in song_title if ch.isalnum())
            file_name = title + "_" + artist_name + ".txt"
            path = folder_name + file_name
            with open(path, "w") as f:
                f.write(lyrics)

    print("[FOUND LYRICS]", len(playlist_lyrics), "songs")

    return playlist_lyrics

def analyze_playlists(sp):
    playlist_data = sp.current_user_playlists()
    information = []
    for playlist in playlist_data['items']:
        id = playlist['id']
        num_tracks = playlist['tracks']['total']
        name = playlist['name']
        if(num_tracks != 0): curr_dataframe = get_playlist_tracks(sp, id, num_tracks)
        else: continue
        names = curr_dataframe['Name'].tolist()
        artists = curr_dataframe['Artist'].tolist()
        zipped = list(zip(names, artists))

        curr_avg_vals = get_average_values_from_playlist(curr_dataframe, zipped)
        curr_emotion = classify_song_emotion((curr_avg_vals['Danceability'],
                                              curr_avg_vals['Energy'],
                                              curr_avg_vals['Tempo'],
                                              curr_avg_vals['Valence']))
        curr_dict = {'name' : name, 'dataframe' : curr_dataframe, 'averages' : curr_avg_vals, 'emotion' : curr_emotion}
        information.append(curr_dict)

    return information

def add_to_tracks(df, new_tracks):
    df = df.append(new_tracks, ignore_index = True)
    return df

def get_tracks_in_date_range(min_time, max_time, df):
    def inRange(row):
        time_string = row["Time"]
        corresonding_time = datetime.datetime.strptime(time_string,"%Y-%m-%dT%H:%M:%S.%fZ")
        return min_time < corresonding_time and corresonding_time < max_time
    return df[df.apply(inRange, axis=1)]

def get_mood_in_date_range(min_time, max_time, tracks):
    pd = get_tracks_in_date_range(min_time, max_time, tracks)




def get_tracks_from_raw_rec(data):
    tracks = []
    for p in data['tracks']:
        song_title = p['name']
        artist_name = p['artists'][0]['name']
        link = p['external_urls']['spotify']
        uri = p['uri']
        curr_dict = {'title' : song_title, 'artist' : artist_name, 'link' : link, 'uri' : uri}
        tracks.append(curr_dict)

    return tracks

def get_spotify_ids(sp, queries, type='track'):
    if not queries:
        return queries

    key = type + 's'
    ids = []
    for q in queries:
        res = sp.search(q, limit=1, offset=0, type=type)
        id = res[key]['items'][0]['id']
        ids.append(id)

    return ids

def get_recommendations(sp, seed_artists=None, seed_genres=None, seed_tracks=None, attributes=None, limit=10):
    seed_artist_ids = get_spotify_ids(sp, seed_artists, 'artist')
    seed_track_ids = get_spotify_ids(sp, seed_tracks, 'track')

    if attributes:
        recs = sp.recommendations(seed_artists=seed_artist_ids, seed_genres=seed_genres, seed_tracks=seed_track_ids, limit=limit, **attributes)
    else:
        recs = sp.recommendations(seed_artists=seed_artist_ids, seed_genres=seed_genres, seed_tracks=seed_track_ids, limit=limit)
    return get_tracks_from_raw_rec(recs)




def add_timestamps(df):
    start_date = datetime.datetime.now() + datetime.timedelta(days=-df.shape[0])
    df['Time'] = [start_date + datetime.timedelta(days=i) for i in range(df.shape[0])]


def add_sentiment_data(df, all_lyrics):
    sent_score = [random.random() for l in all_lyrics]
    sent_mag = [random.random() for l in all_lyrics]

    sent_score = []
    sent_mag = []

    batch_size = 10
    for i in range(0, len(all_lyrics), batch_size):
        res = sentiment_analysis.analyze_text_sentiment_batch(all_lyrics[i: min(i+batch_size, len(all_lyrics))])
        sent_score += [r['score'] for r in res]
        sent_mag += [r['magnitude'] for r in res]
        save_df = pd.DataFrame(data=[sent_score, sent_mag])
        save_df.to_csv("temp_save/temp" + str(i) + ".csv")

    df['sentiment_score'] = sent_score
    df['sentiment_mag'] = sent_mag



def get_recent_moods(sp):
    df = get_current_user_recently_played(sp)
    tracks = [(row['Name'], row['Artist']) for i, row in df.iterrows()]
    all_lyrics = lyrics_getter.get_song_lyrics_batch(tracks)

    raw_lyrics = []

    lyrics_dict = {l[0][0]: l[1] for l in all_lyrics}

    all_data = []
    for index, row in df.iterrows():
        if row['Name'] in lyrics_dict:
            new_row = list(row)
            all_data += [new_row]
            raw_lyrics += [lyrics_dict[row['Name']]]

    df = pd.DataFrame(data=all_data, columns=df.columns)

    add_timestamps(df)

    add_sentiment_data(df, raw_lyrics)

    times = [row['Time'] for i,row in df.iterrows()]
    moods = [calculate_emotion(row['sentiment_score'] * row['sentiment_mag'], row['Danceability'], row['Energy'], row['Tempo'], row['Valence'])
                for i,row in df.iterrows()]


    return pd.DataFrame({"Time": times, "Mood":moods})



if __name__ == "__main__":
    sp = init_spotify()

    mood_data = get_recent_moods(sp)

    print(mood_data)

    playlists = get_current_user_playlists(sp)
    print(playlists)
    print()
    for name, id, num_tracks in playlists:
        folder_name = "lyrics/" + name + "/"
        if os.path.isdir(folder_name):
            shutil.rmtree(folder_name)
        os.makedirs(folder_name)
    for name, id, num_tracks in playlists:
        playlist_lyrics = get_playlist_lyrics(sp, name, id, num_tracks)
        print()
