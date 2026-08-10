import struct
import json

def read_glb():
    try:
        with open('solaire.glb', 'rb') as f:
            magic = f.read(4)
            if magic != b'glTF':
                print("Not a valid GLB file")
                return
            version = struct.unpack('<I', f.read(4))[0]
            length = struct.unpack('<I', f.read(4))[0]
            
            chunk_length = struct.unpack('<I', f.read(4))[0]
            chunk_type = f.read(4)
            if chunk_type != b'JSON':
                print("First chunk is not JSON")
                return
            
            json_data = f.read(chunk_length).decode('utf-8')
            gltf = json.loads(json_data)
            
            print("Nodes found in GLTF:")
            if 'nodes' in gltf:
                for idx, node in enumerate(gltf['nodes']):
                    name = node.get('name', 'unnamed_node')
                    print(f"[{idx}] {name}")
            else:
                print("No nodes found in GLTF!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    read_glb()
