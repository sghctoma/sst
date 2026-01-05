import json
import sys

def get_choice(prompt, options, default_index=0):
    print(f"\n{prompt}")
    for i, opt in enumerate(options):
        default_str = " (default)" if i == default_index else ""
        print(f"  {i+1}. {opt['display_name']}{default_str}")
    
    while True:
        choice = input(f"Select [1-{len(options)}, default {default_index+1}]: ").strip()
        if not choice:
            return options[default_index]
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            pass
        print(f"Invalid choice. Please enter a number between 1 and {len(options)}.")

def generate():
    print("SST Firmware Configuration Generator")
    print("====================================")

    boards = [
        {"name": "pico", "variable": "pico_w", "display_name": "Pico W"},
        {"name": "pico2", "variable": "pico2_w", "display_name": "Pico 2 W"}
    ]

    microsd_options = [
        {"name": "spi", "variables": {"SPI_MICROSD": "ON"}, "display_name": "SPI MicroSD"},
        {"name": "sdio", "variables": {"SPI_MICROSD": "OFF"}, "display_name": "SDIO MicroSD"}
    ]

    display_options = [
        {"name": "i2c", "variables": {"DISP_PROTO": "PIO_I2C"}, "display_name": "I2C display"},
        {"name": "spi", "variables": {"DISP_PROTO": "SPI"}, "display_name": "SPI display"}
    ]

    fork_options = [
        {"name": "as5600", "variables": {"FORK_LINEAR": "OFF"}, "display_name": "AS5600 fork"},
        {"name": "linear", "variables": {"FORK_LINEAR": "ON"}, "display_name": "Linear fork (ADC)"}
    ]

    shock_options = [
        {"name": "as5600", "variables": {"SHOCK_LINEAR": "OFF"}, "display_name": "AS5600 shock"},
        {"name": "linear", "variables": {"SHOCK_LINEAR": "ON"}, "display_name": "Linear shock (ADC)"}
    ]

    imu_models = [
        {"name": "NONE", "display_name": "None"},
        {"name": "MPU6050", "display_name": "MPU6050"},
        {"name": "LSM6DSO", "display_name": "LSM6DSO"}
    ]

    imu_protos = [
        {"name": "I2C", "display_name": "I2C"},
        {"name": "SPI", "display_name": "SPI"}
    ]

    # Defaults: spi microsd, i2c display, as5600 fork, as5600 shock, 
    # mpu6050 frame imu, lsm6dso i2c fork imu, none rear imu.

    board = get_choice("Select Board:", boards, 1) # Default Pico 2
    microsd = get_choice("Select MicroSD connection:", microsd_options, 0) # Default SPI
    display = get_choice("Select Display connection:", display_options, 0) # Default I2C
    fork = get_choice("Select Fork sensor:", fork_options, 0) # Default AS5600
    shock = get_choice("Select Shock sensor:", shock_options, 0) # Default AS5600
    
    print("\n--- IMU Configuration ---")
    
    frame_imu_model = get_choice("Frame IMU Model:", imu_models, 1) # Default MPU6050
    frame_imu_proto = {"name": "I2C"}
    if frame_imu_model['name'] == "LSM6DSO":
        frame_imu_proto = get_choice("Frame IMU Protocol:", imu_protos, 0)
    elif frame_imu_model['name'] == "NONE":
        frame_imu_proto = {"name": ""}

    fork_imu_model = get_choice("Fork IMU Model:", imu_models, 2) # Default LSM6DSO
    fork_imu_proto = {"name": "I2C"}
    if fork_imu_model['name'] == "LSM6DSO":
        fork_imu_proto = get_choice("Fork IMU Protocol:", imu_protos, 0) # Default I2C
    elif fork_imu_model['name'] == "NONE":
        fork_imu_proto = {"name": ""}

    rear_imu_model = get_choice("Rear IMU Model:", imu_models, 0) # Default None
    rear_imu_proto = {"name": "I2C"}
    if rear_imu_model['name'] == "LSM6DSO":
        rear_imu_proto = get_choice("Rear IMU Protocol:", imu_protos, 0)
    elif rear_imu_model['name'] == "NONE":
        rear_imu_proto = {"name": ""}

    # Construct the cache variables
    cache_variables = {
        "PICO_BOARD": board['variable'],
        "IMU_FRAME": frame_imu_model['name'],
        "IMU_FRAME_PROTO": frame_imu_proto['name'],
        "IMU_FORK": fork_imu_model['name'],
        "IMU_FORK_PROTO": fork_imu_proto['name'],
        "IMU_REAR": rear_imu_model['name'],
        "IMU_REAR_PROTO": rear_imu_proto['name']
    }
    cache_variables.update(microsd['variables'])
    cache_variables.update(display['variables'])
    cache_variables.update(fork['variables'])
    cache_variables.update(shock['variables'])

    configure_presets = []
    build_presets = []

    for build_type in ["Release", "Debug"]:
        # Construct a clean name identifier (slug)
        name_parts = [
            board['name'],
            microsd['name'],
            display['name'],
            f"f_{fork['name']}",
            f"s_{shock['name']}"
        ]
        
        if frame_imu_model['name'] != "NONE":
            name_parts.append(f"fr_{frame_imu_model['name'].lower()}")
        if fork_imu_model['name'] != "NONE":
            name_parts.append(f"fo_{fork_imu_model['name'].lower()}")
        if rear_imu_model['name'] != "NONE":
            name_parts.append(f"re_{rear_imu_model['name'].lower()}")
        if all(m['name'] == "NONE" for m in [frame_imu_model, fork_imu_model, rear_imu_model]):
            name_parts.append("no_imu")
            
        name_parts.append(build_type.lower())
        full_preset_name = "-".join(name_parts).replace("_", "") # Remove internal underscores for cleaner slug
        
        # Construct a readable Display Name
        disp_board = board['display_name']
        disp_hw = f"{microsd['name'].upper()} SD, {display['name'].upper()} Disp, {fork['name'].upper()}/{shock['name'].upper()} Sensors"
        
        imu_parts = []
        if frame_imu_model['name'] != "NONE":
            imu_parts.append(f"Frame:{frame_imu_model['name']}")
        if fork_imu_model['name'] != "NONE":
            imu_parts.append(f"Fork:{fork_imu_model['name']}")
        if rear_imu_model['name'] != "NONE":
            imu_parts.append(f"Rear:{rear_imu_model['name']}")
        
        disp_imu = f"IMUs({', '.join(imu_parts)})" if imu_parts else "No IMUs"
        
        display_name = f"{disp_board} ({build_type}): {disp_hw}, {disp_imu}"
        
        vars = cache_variables.copy()
        vars["CMAKE_BUILD_TYPE"] = build_type
        
        config_preset = {
            "name": full_preset_name,
            "displayName": display_name,
            "binaryDir": f"${{sourceDir}}/build/{full_preset_name}",
            "cacheVariables": vars
        }
        configure_presets.append(config_preset)
        
        build_presets.append({
            "name": full_preset_name,
            "configurePreset": full_preset_name
        })

    full_json = {
        "version": 3,
        "cmakeMinimumRequired": {
            "major": 3,
            "minor": 21,
            "patch": 1
        },
        "configurePresets": configure_presets,
        "buildPresets": build_presets
    }

    with open("CMakePresets.json", "w") as f:
        json.dump(full_json, f, indent=2)
    
    print("\nSuccessfully generated CMakePresets.json with your custom configuration.")
    print("You can now build using the 'release' or 'debug' presets in VS Code or via CLI.")

if __name__ == "__main__":
    generate()