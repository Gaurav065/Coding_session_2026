#define PI 3.14159265359
#define TAU 6.28318530718

vec3 hash3(vec3 p) {
    p = fract(p * 0.3183098861837907);
    p *= 17.0;
    return fract(p.xzy * p.yzx * (p + 1.0));
}

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float hash(vec3 p) {
    return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453);
}

vec2 hash2(vec2 p) {
    return fract(sin(vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)))) * 43758.5453);
}

vec3 hash33(vec3 p) {
    return fract(sin(vec3(dot(p, vec3(127.1, 311.7, 74.7)), dot(p, vec3(269.5, 183.3, 246.1)), dot(p, vec3(113.1, 71.7, 311.7)))) * 43758.5453);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
}

float fbm(vec2 p, int octaves) {
    float value = 0.0;
    float amplitude = 0.5;
    for (int i = 0; i < 8; i++) {
        if (i >= octaves) break;
        value += amplitude * noise(p);
        p *= 2.0;
        amplitude *= 0.5;
    }
    return value;
}

vec3 starColor(float temp) {
    float h = clamp((temp - 2000.0) / 10000.0, 0.0, 1.0);
    vec3 c = vec3(1.0);
    c.r = 1.0 - smoothstep(0.0, 0.4, h) + 0.2 * smoothstep(0.6, 1.0, h);
    c.g = smoothstep(0.0, 0.3, h) * (1.0 - smoothstep(0.5, 0.8, h));
    c.b = smoothstep(0.4, 0.9, h);
    return c;
}

float starMagnitude(float mass) {
    return -2.5 * (log(pow(mass, 3.5)) / log(10.0)) + 4.74;
}

vec3 sampleStarField(vec3 dir, float time, float seed) {
    vec3 color = vec3(0.0);
    float starDensity = 8000.0;
    
    for (int layer = 0; layer < 3; layer++) {
        float layerSeed = seed + float(layer) * 1000.0;
        float density = starDensity * (1.0 + float(layer) * 0.5);
        float scale = 1.0 + float(layer) * 0.3;
        
        vec3 sampleDir = dir * scale;
        vec2 uv = vec2(atan(sampleDir.z, sampleDir.x), asin(clamp(sampleDir.y, -1.0, 1.0)));
        uv.x += PI;
        uv.y += PI * 0.5;
        uv *= density * 0.01;
        
        vec2 cell = floor(uv);
        vec2 f = fract(uv);
        
        for (int dx = -1; dx <= 1; dx++) {
            for (int dy = -1; dy <= 1; dy++) {
                vec2 neighbor = cell + vec2(float(dx), float(dy));
                vec3 h = hash33(vec3(neighbor, layerSeed));
                
                vec2 starPos = neighbor + h.xy;
                vec2 toStar = starPos - uv;
                float dist = length(toStar);
                
                float mag = mix(12.0, 4.0, h.z);
                float size = pow(10.0, -mag / 5.0) * 0.008;
                float temp = mix(2500.0, 40000.0, h.x);
                vec3 starCol = starColor(temp);
                
                float brightness = pow(1.0 - smoothstep(0.0, size, dist), 3.0);
                brightness *= mix(0.7, 1.3, h.y);
                
                float twinkle = 0.95 + 0.05 * sin(time * 2.0 + h.x * 50.0 + h.y * 30.0);
                brightness *= twinkle;
                
                float glare = smoothstep(size * 10.0, size, dist);
                color += starCol * brightness * (1.0 + glare * 0.3);
            }
        }
    }
    
    float nebula = fbm(dir.xz * 0.5 + time * 0.001, 4) * 0.02;
    color += vec3(0.3, 0.1, 0.5) * nebula * smoothstep(-0.2, 0.2, dir.y);
    
    return color;
}

uniform float uTime;
uniform float uExposure;
uniform vec2 uResolution;
varying vec3 vDir;

void main() {
    vec3 col = sampleStarField(vDir, uTime, 42.0);
    col = pow(col, vec3(1.0 / 2.2));
    col *= uExposure;
    gl_FragColor = vec4(col, 1.0);
}