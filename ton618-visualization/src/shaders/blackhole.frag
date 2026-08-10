#define PI 3.14159265359
#define TAU 6.28318530718
#define MAX_STEPS 128
#define MAX_DIST 1000.0
#define EPSILON 0.001

uniform float uTime;
uniform float uExposure;
uniform vec3 uCameraPos;
uniform float uRs;
uniform float uSpin;
uniform vec2 uResolution;
uniform bool uHighQuality;

varying vec3 vWorldPos;
varying vec3 vViewDir;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float hash(vec3 p) { return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
vec2 hash2(vec2 p) { return fract(sin(vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)))) * 43758.5453); }
vec3 hash3(vec3 p) { return fract(sin(vec3(dot(p, vec3(127.1, 311.7, 74.7)), dot(p, vec3(269.5, 183.3, 246.1)), dot(p, vec3(113.1, 71.7, 311.7)))) * 43758.5453); }

float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1,0)), f.x), mix(hash(i + vec2(0,1)), hash(i + vec2(1,1)), f.x), f.y);
}

float fbm(vec2 p, int oct) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 6; i++) {
        if (i >= oct) break;
        v += a * noise(p);
        p *= 2.0; a *= 0.5;
    }
    return v;
}

vec3 accretionColor(float r, float beaming) {
    float t = clamp((r - 1.0) / 15.0, 0.0, 1.0);
    vec3 color = vec3(1.0);
    
    if (t < 0.1) {
        color = mix(vec3(1.0, 0.9, 0.8), vec3(1.0, 0.7, 0.2), t / 0.1);
    } else if (t < 0.4) {
        color = mix(vec3(1.0, 0.7, 0.2), vec3(0.8, 0.2, 0.05), (t - 0.1) / 0.3);
    } else {
        color = mix(vec3(0.8, 0.2, 0.05), vec3(0.1, 0.0, 0.0), (t - 0.4) / 0.6);
    }
    
    // Shift color slightly based on doppler beaming (blue shift vs red shift)
    color = mix(color * vec3(1.0, 0.4, 0.1), color * vec3(0.8, 1.0, 1.0), clamp((beaming - 0.5) / 2.0, 0.0, 1.0));
    return color;
}

float diskDensity(float r, float theta, float time) {
    float base = smoothstep(1.0, 1.2, r) * (1.0 - smoothstep(10.0, 15.0, r));
    float spiral = 0.2 * sin(6.0 * theta - 0.8 * log(r) - time * 0.2);
    
    // Very smooth, flat disk
    return base * (1.0 + spiral);
}

float diskHeight(float r) {
    return 0.02 * r * (1.0 + 0.1 * sin(r * 3.0));
}

vec3 gravLens(vec3 rayDir, vec3 pos, float rs, float spin) {
    vec3 dir = rayDir;
    vec3 p = pos;
    float dt = 0.4; // Extremely large steps for background lensing
    for (int i = 0; i < 16; i++) {
        float r = length(p);
        if (r < rs * 1.01) break;
        
        vec3 gravity = -p / (r * r * r);
        float frameDrag = spin * 0.5 * dot(cross(p, dir), vec3(0,1,0)) / (r * r * r);
        dir += gravity * dt;
        dir = normalize(dir + vec3(-dir.y * frameDrag, dir.x * frameDrag, 0.0) * dt);
        p += dir * dt;
    }
    return normalize(p);
}

vec3 tracePhotonRing(vec3 ro, vec3 rd, float rs, float spin) {
    vec3 color = vec3(0.0);
    int maxSteps = uHighQuality ? 48 : 32;
    float dt = 0.04;
    
    for (int i = 0; i < 96; i++) {
        if (i >= maxSteps) break;
        float r = length(ro);
        if (r < rs * 1.05) { color = vec3(0.0); break; }
        if (r > MAX_DIST) break;
        
        float b = length(cross(ro, rd));
        float r_min = 1.5 * rs;
        if (b < r_min * 1.2 && b > r_min * 0.8) {
            float intensity = smoothstep(r_min * 1.05, r_min, b) * smoothstep(r_min * 0.95, r_min, b);
            vec3 c = vec3(1.0, 0.85, 0.6);
            color += c * intensity * 5.0 * exp(-(r - r_min) * (r - r_min) * 20.0);
        }
        
        vec3 gravity = -ro / (r * r * r);
        float frameDrag = spin * 0.3 * dot(cross(ro, rd), vec3(0,1,0)) / (r * r * r);
        rd += gravity * dt;
        rd = normalize(rd + vec3(-rd.y * frameDrag, rd.x * frameDrag, 0.0) * dt);
        ro += rd * dt;
    }
    return color;
}

vec3 sampleDisk(vec3 pos, float time) {
    float r = length(pos.xz);
    float theta = atan(pos.z, pos.x);
    float h = abs(pos.y);
    float H = diskHeight(r);
    
    if (r < 1.0 || r > 25.0 || h > H * 3.0) return vec3(0.0);
    
    float dens = diskDensity(r, theta, time);
    float vertical = 1.0 - smoothstep(0.0, H, h);
    float density = dens * vertical;
    
    if (density < 0.001) return vec3(0.0);
    
    float doppler = 1.0;
    float v_phi = sqrt(1.5 / r) * (1.0 - 0.1 * uSpin);
    vec3 vel = vec3(-v_phi * sin(theta), 0.0, v_phi * cos(theta));
    float v_los = dot(vel, normalize(vViewDir));
    
    doppler = 1.0 / (1.0 - v_los * 0.8);
    float beaming = pow(clamp(doppler, 0.2, 3.5), 3.0);
    
    vec3 col = accretionColor(r, beaming);
    
    float redshift = 1.0 / sqrt(1.0 - 1.0 / r);
    redshift = clamp(redshift, 0.5, 2.0);
    
    return col * density * beaming * 1.5 / redshift;
}

vec3 starBackground(vec3 dir) {
    vec3 col = vec3(0.0);
    for (int layer = 0; layer < 1; layer++) {
        float seed = 1234.0 + float(layer) * 100.0;
        float density = 5000.0 * (1.0 + float(layer) * 0.3);
        vec2 uv = vec2(atan(dir.z, dir.x), asin(clamp(dir.y, -1.0, 1.0)));
        uv.x += PI; uv.y += PI * 0.5;
        uv *= density * 0.01;
        vec2 cell = floor(uv), f = fract(uv);
        for (int dx = -1; dx <= 1; dx++) {
            for (int dy = -1; dy <= 1; dy++) {
                vec2 n = cell + vec2(float(dx), float(dy));
                vec3 h = hash3(vec3(n, seed));
                vec2 starPos = n + h.xy;
                vec2 toStar = starPos - uv;
                float dist = length(toStar);
                float mag = mix(12.0, 5.0, h.z);
                float size = pow(10.0, -mag / 5.0) * 0.006;
                float temp = mix(2500.0, 40000.0, h.x);
                float h2 = clamp((temp - 2000.0) / 10000.0, 0.0, 1.0);
                vec3 starCol = vec3(1.0);
                starCol.r = 1.0 - smoothstep(0.0, 0.4, h2) + 0.2 * smoothstep(0.6, 1.0, h2);
                starCol.g = smoothstep(0.0, 0.3, h2) * (1.0 - smoothstep(0.5, 0.8, h2));
                starCol.b = smoothstep(0.4, 0.9, h2);
                float brightness = pow(1.0 - smoothstep(0.0, size, dist), 3.0) * mix(0.7, 1.3, h.y);
                brightness *= 0.95 + 0.05 * sin(uTime * 2.0 + h.x * 50.0);
                col += starCol * brightness;
            }
        }
    }
    return col;
}

void main() {
    vec3 ro = uCameraPos;
    vec3 rd = normalize(vViewDir);
    
    float rs = uRs;
    float spin = uSpin;
    
    vec3 color = vec3(0.0);
    float transmittance = 1.0;
    
    color += tracePhotonRing(ro, rd, rs, spin);
    
    float steps = uHighQuality ? 128.0 : 80.0;
    vec3 pos = ro;
    vec3 dir = rd;
    
    for (int i = 0; i < 256; i++) {
        if (i >= int(steps)) break;
        float r = length(pos);
        if (r < rs * 1.01) { color = vec3(0.0); transmittance = 0.0; break; }
        if (r > MAX_DIST) break;
        
        // Dynamic step sizing: take large steps far away, small steps near the black hole
        float dt = max(0.05, 0.08 * r);
        
        vec3 diskCol = sampleDisk(pos, uTime);
        if (length(diskCol) > 0.0) {
            float alpha = min(length(diskCol) * 0.5 * dt, 0.95);
            color += diskCol * alpha * transmittance;
            transmittance *= (1.0 - alpha);
            if (transmittance < 0.01) break;
        }
        
        // Ray bending (gravitational lensing)
        vec3 gravity = -pos / (r * r * r);
        dir += gravity * dt;
        dir = normalize(dir);
        
        pos += dir * dt;
    }
    
    // Background starfield (warped by gravity)
    if (transmittance > 0.01) {
        vec3 bgDir = gravLens(rd, ro, rs, spin);
        color += starBackground(bgDir) * transmittance;
    }
    
    color = pow(color, vec3(1.0 / 2.2));
    color *= uExposure;
    
    float vignette = 1.0 - 0.3 * pow(1.0 - dot(normalize(vViewDir), vec3(0,0,-1)), 2.0);
    color *= vignette;
    
    gl_FragColor = vec4(color, 1.0);
}