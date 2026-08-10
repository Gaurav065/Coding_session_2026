const clientId = '1058bbee5bdc49b7b4974e3d90ea4703';
const clientSecret = '537280641f41464cad9e25e666d2d5ed';
const redirectUri = 'http://127.0.0.1:8000/';

let token = null;
let deviceId = null;
let player = null;
let progressInterval = null;

// --- Auth Helpers ---
function loginToSpotify() {
    const scope = [
        'streaming',
        'user-read-email',
        'user-read-private',
        'user-library-read',
        'user-read-playback-state',
        'user-modify-playback-state',
        'user-top-read'
    ].join(' ');

    const authUrl = new URL("https://accounts.spotify.com/authorize");
    
    const params = {
      response_type: 'code',
      client_id: clientId,
      scope: scope,
      redirect_uri: redirectUri,
    }

    authUrl.search = new URLSearchParams(params).toString();
    window.location.href = authUrl.toString();
}

async function fetchTokenFromCode(code) {
    const response = await fetch('https://accounts.spotify.com/api/token', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic ' + btoa(clientId + ':' + clientSecret)
        },
        body: new URLSearchParams({
            grant_type: 'authorization_code',
            code: code,
            redirect_uri: redirectUri,
        }),
    });

    const data = await response.json();
    if (data.access_token) {
        localStorage.setItem('access_token', data.access_token);
        if (data.refresh_token) {
            localStorage.setItem('refresh_token', data.refresh_token);
        }
        return data.access_token;
    } else {
        console.error("Error fetching token:", data);
        alert("Failed to get token: " + (data.error_description || data.error));
        return null;
    }
}

// --- API Helpers ---
async function fetchWebApi(endpoint, method, body) {
  const res = await fetch(`https://api.spotify.com/${endpoint}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
    method,
    body: body ? JSON.stringify(body) : undefined
  });
  
  if (res.status === 401) {
      alert("Session expired. Please log in again.");
      localStorage.removeItem('access_token');
      window.location.reload();
  }
  
  if (res.status === 204) return null;
  return await res.json();
}

async function getTopTracks() {
  const data = await fetchWebApi('v1/me/top/tracks?time_range=short_term&limit=20', 'GET');
  if (data && data.items) {
      return data.items;
  } else if (data && data.error) {
      console.error("Spotify API Error:", data.error);
      return [];
  }
  return [];
}

async function getLikedSongs() {
  const data = await fetchWebApi('v1/me/tracks?limit=20', 'GET');
  if (data && data.items) {
      // Extract the 'track' object from the saved track wrapper
      return data.items.map(item => item.track);
  } else if (data && data.error) {
      console.error("Spotify API Error:", data.error);
      return [];
  }
  return [];
}

async function getPlaylists() {
  const data = await fetchWebApi('v1/me/playlists?limit=20', 'GET');
  if (data && data.items) {
      return data.items;
  }
  return [];
}

async function playTrack(uri) {
    if (!deviceId) {
        alert("The Spotify Player is still connecting. Please wait a few seconds until the player bar says 'Ready to Play!', then try again. (If it never connects, try disabling adblockers or checking if third-party cookies are blocked).");
        return;
    }
    await fetchWebApi(`v1/me/player/play?device_id=${deviceId}`, 'PUT', {
        uris: [uri]
    });
}

async function playContext(contextUri) {
    if (!deviceId) {
        alert("The Spotify Player is still connecting. Please wait...");
        return;
    }
    await fetchWebApi(`v1/me/player/play?device_id=${deviceId}`, 'PUT', {
        context_uri: contextUri
    });
}

function formatTime(ms) {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

function updateProgressBar(position, duration) {
    const fill = document.getElementById('progress-fill');
    const timeCurrent = document.querySelector('.time-current');
    const timeTotal = document.querySelector('.time-total');
    
    if (duration > 0) {
        const percentage = (position / duration) * 100;
        fill.style.width = `${percentage}%`;
        timeCurrent.textContent = formatTime(position);
        timeTotal.textContent = formatTime(duration);
    }
}

// --- UI Rendering ---
function renderTracks(tracks, title) {
    document.getElementById('section-title').textContent = title;
    const container = document.getElementById('top-tracks-container');
    container.innerHTML = ''; 

    tracks.forEach(track => {
        const card = document.createElement('div');
        card.className = 'track-card';
        
        const imageUrl = track.album.images[0]?.url || 'https://via.placeholder.com/150';
        const artistNames = track.artists.map(a => a.name).join(', ');

        card.innerHTML = `
            <img src="${imageUrl}" alt="${track.name}">
            <div class="track-name" title="${track.name}">${track.name}</div>
            <div class="track-artists" title="${artistNames}">${artistNames}</div>
        `;

        card.addEventListener('click', () => {
            playTrack(track.uri);
            // Don't update UI here immediately, let the player_state_changed event handle it
        });

        container.appendChild(card);
    });
}

function updateNowPlayingUI(track) {
    document.getElementById('np-title').textContent = track.name;
    document.getElementById('np-artist').textContent = track.artists.map(a => a.name).join(', ');
    document.getElementById('np-image').src = track.album.images[0]?.url || 'https://via.placeholder.com/56';
    document.getElementById('btn-toggle-play').textContent = '⏸️'; 
}

function renderPlaylists(playlists, title) {
    document.getElementById('section-title').textContent = title;
    const container = document.getElementById('top-tracks-container');
    container.innerHTML = ''; 

    playlists.forEach(playlist => {
        const card = document.createElement('div');
        card.className = 'track-card';
        
        const imageUrl = playlist.images[0]?.url || 'https://via.placeholder.com/150';
        const ownerName = playlist.owner.display_name;

        card.innerHTML = `
            <img src="${imageUrl}" alt="${playlist.name}">
            <div class="track-name" title="${playlist.name}">${playlist.name}</div>
            <div class="track-artists" title="${ownerName}">${ownerName}</div>
        `;

        card.addEventListener('click', () => {
            playContext(playlist.uri);
        });

        container.appendChild(card);
    });
}

// --- Web Playback SDK Initialization ---
function initializeSpotifyPlayer() {
    window.onSpotifyWebPlaybackSDKReady = () => {
        console.log("Spotify Web Playback SDK Ready");

        player = new Spotify.Player({
            name: 'Vanilla Web Player Clone',
            getOAuthToken: cb => { cb(token); },
            volume: 0.5
        });

        player.addListener('ready', ({ device_id }) => {
            console.log('Ready with Device ID', device_id);
            deviceId = device_id;
            document.getElementById('np-title').textContent = "Ready to Play!";
            document.getElementById('np-artist').textContent = "Select a track above";
        });

        player.addListener('not_ready', ({ device_id }) => {
            console.log('Device ID has gone offline', device_id);
        });

        player.addListener('initialization_error', ({ message }) => { console.error(message); });
        player.addListener('authentication_error', ({ message }) => { 
            console.error("Auth error:", message); 
            alert("Authentication failed. Please log in again.");
            localStorage.removeItem('access_token');
            loginToSpotify();
        });
        player.addListener('account_error', ({ message }) => { console.error("Account error:", message); });

        player.addListener('player_state_changed', state => {
            if (!state) return;
            
            const currentTrack = state.track_window.current_track;
            if (currentTrack) {
                document.getElementById('np-title').textContent = currentTrack.name;
                document.getElementById('np-artist').textContent = currentTrack.artists.map(a => a.name).join(', ');
                document.getElementById('np-image').src = currentTrack.album.images[0]?.url || 'https://via.placeholder.com/56';
            }

            const playBtn = document.getElementById('btn-toggle-play');
            playBtn.textContent = state.paused ? '▶️' : '⏸️';

            // Update Progress Bar
            updateProgressBar(state.position, state.duration);
            
            if (progressInterval) clearInterval(progressInterval);
            
            if (!state.paused) {
                let currentPosition = state.position;
                progressInterval = setInterval(() => {
                    currentPosition += 1000;
                    if (currentPosition <= state.duration) {
                        updateProgressBar(currentPosition, state.duration);
                    }
                }, 1000);
            }
        });

        player.connect();
    };

    // Dynamically inject the script so it definitely loads AFTER we set the token
    const script = document.createElement('script');
    script.src = "https://sdk.scdn.co/spotify-player.js";
    script.async = true;
    document.body.appendChild(script);
}

// --- Initialization & Event Listeners ---
async function init() {
    const authBtn = document.getElementById('auth-btn');
    
    // Check for authorization code in URL
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');

    if (code) {
        // Exchange code for token using client secret
        token = await fetchTokenFromCode(code);
        // Clear the URL code
        window.history.replaceState({}, document.title, window.location.pathname);
    } else {
        // Check for existing token in localStorage
        token = localStorage.getItem('access_token');
    }

    if (!token) {
        document.getElementById('top-tracks-container').innerHTML = 'Please log in to view your top tracks.';
        authBtn.textContent = 'Log in / Premium';
        authBtn.addEventListener('click', loginToSpotify);
    } else {
        authBtn.textContent = 'Logged In';
        authBtn.style.backgroundColor = '#1ed760'; // Spotify green
        authBtn.style.color = '#000';
        authBtn.addEventListener('click', () => {
            if(confirm("Log out?")) {
                localStorage.clear();
                window.location.reload();
            }
        });

        const container = document.getElementById('top-tracks-container');
        
        async function loadHome() {
            document.getElementById('nav-home').classList.add('active');
            document.getElementById('nav-liked').classList.remove('active');
            document.getElementById('nav-library').classList.remove('active');
            container.innerHTML = 'Loading your top tracks...';
            const tracks = await getTopTracks();
            if (tracks.length > 0) {
                renderTracks(tracks, "Your Top Tracks");
            } else {
                container.innerHTML = 'No tracks found. Make sure you listen to music on Spotify!';
            }
        }

        async function loadLikedSongs() {
            document.getElementById('nav-home').classList.remove('active');
            document.getElementById('nav-liked').classList.add('active');
            document.getElementById('nav-library').classList.remove('active');
            container.innerHTML = 'Loading your liked songs...';
            const tracks = await getLikedSongs();
            if (tracks.length > 0) {
                renderTracks(tracks, "Liked Songs");
            } else {
                container.innerHTML = 'No liked songs found in your library.';
            }
        }

        async function loadLibrary() {
            document.getElementById('nav-home').classList.remove('active');
            document.getElementById('nav-liked').classList.remove('active');
            document.getElementById('nav-library').classList.add('active');
            container.innerHTML = 'Loading your playlists...';
            const playlists = await getPlaylists();
            if (playlists.length > 0) {
                renderPlaylists(playlists, "Your Playlists");
            } else {
                container.innerHTML = 'No playlists found.';
            }
        }

        document.getElementById('nav-home').addEventListener('click', loadHome);
        document.getElementById('nav-liked').addEventListener('click', loadLikedSongs);
        document.getElementById('nav-library').addEventListener('click', loadLibrary);

        // Load home by default
        await loadHome();
        // NOW we initialize the player since we have the token
        initializeSpotifyPlayer();

        // Setup Player Controls
        document.getElementById('btn-toggle-play').addEventListener('click', () => {
            if (player) player.togglePlay();
        });
        
        document.getElementById('btn-prev').addEventListener('click', () => {
            if (player) player.previousTrack();
        });

        document.getElementById('btn-next').addEventListener('click', () => {
            if (player) player.nextTrack();
        });

        // Setup Progress Bar Seeking
        const progressBar = document.querySelector('.progress-bar');
        progressBar.addEventListener('click', async (e) => {
            if (!player) return;
            const state = await player.getCurrentState();
            if (!state) return;
            
            const rect = progressBar.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            const percentage = clickX / rect.width;
            const seekMs = Math.floor(state.duration * percentage);
            
            player.seek(seekMs);
        });
    }
}

// Start app
init();
