varying vec3 vWorldPos;
varying vec3 vViewDir;


void main() {
    vec4 worldPos = modelMatrix * vec4(position, 1.0);
    vWorldPos = worldPos.xyz;
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    vViewDir = normalize(vWorldPos - cameraPosition);
    gl_Position = projectionMatrix * mvPosition;
}