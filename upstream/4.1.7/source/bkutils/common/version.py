import yaml
import os
bk_ver = 'v1.1.0.5'

def get_tool_version():
    try:
        yaml_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config', 'version.yaml')
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            version = data['version'] if data and 'version' in data else None
        return version.split('+')[0] + f".{int(version.split('+')[1][-3:])}" if version else bk_ver
    except Exception as e:
        return bk_ver
if __name__ == '__main__':
    print(get_tool_version())
