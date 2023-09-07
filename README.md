# INODEMODBUS 
INODEMODBUS service for queries to Modbus devices via TCP/RTU protocol

# Requirements
Before starting to deploy INODEMODBUS services must be in operation other services on which it depends directly:
1. MQTT broker: preferably Mosquitto, but any MQTT broker will serve. The parameters for connection to the INODEMODBUS service shall be indicated in the configuration.
2. MongoDB: there must be an instance of MongoDB containing a database called `inode_modbus_config` and in it a `config` collection which will store documents in the following format:


    ``` json
    {
        "operator_id": "operator_UNIQUE_id_string",
        "mongo_config": {
            "conn_str": "mongodb://user:password@IP:PORT/?authMechanism=DEFAULT"
        },
        "modbus_config": {
            "modbus_addr": 1,
            "modbus_type": "tcp",
            "endian_bytes": "BIG",
            "endian_words": "BIG",
            "tcp_config": {
                "tcp_host": "IP", <-- modbus TCP IP
                "tcp_port": 502        <-- modbus TCP PORT
            },
            "rtu_config": {
                "rtu_port": "COM9",
                "rtu_baudrate": 9600,
                "rtu_bitsize": 8,
                "rtu_parity": "N",
                "rtu_stopbit": 1,
                "timeout": 10
            },
            "mqtt_config": {
                "mqtt_broker": "IP",
                "mqtt_port": 1883,
                "mqtt_id": "operator_mqtt_UNIQUE_id",
                "mqtt_user": "user",
                "mqtt_passwd": "password",
                "mqtt_topic": "topic"
            },
            "autoquery_config": {
                "enabled": false,
                "intervalms": 1000, <-- miliseconds
                "registers": {
                    "holdingstring": [], <-- [number]
                    "holdingbits": [],
                    "holdingint8": [],
                    "holdinguint8": [],
                    "holdingint16": [],
                    "holdingint32": [],
                    "holdinguint16": [],
                    "holdinguint32": [],
                    "holdingf16": [],
                    "holdingf32": [],
                    "discrete_input": [],
                    "input": []
                }
            },
            "keep_reg": 1,
            "_regLen": "16",
            "reg_shift": 0 <-- Setup register shift if needed
        }
    }
    ```

# Installation
1.  **Docker**

    To install this service, the `CONFIG.json` file must be configured with an `operator_id` that exists in the database, so that the stored configuration can be loaded if it exists.

    * We create the image: `sudo docker build -t inodemodbuspython:latest. `
    * We test the execution: `sudo docker run -it inodemodbuspython:latest`
    * We launch the service unattended (this will automatically start in case of system failure or restart):

        `docker run -d --restart always inodemodbuspython:latest`

    * Force a service to stop manually: `docker kill inodemodbuspython:latest`
    * We should note that if the reboot policy indicated in the start parameters of the container is `always` (`-restart <always | unless-stopped | no>`). This policy must be updated to `unless-stopped` or `no` in order to make a container stop
    * To move the generated image to other systems we can compress it and then move it to the desired host: `sudo docker save -o inodemodbuspython.zip inodemodbuspython`
    * After copying it to the new system we can register it in your Docker: `sudo docker load -i inodemodbuspython.zip`
    * And we can test again the execution or launch the service unattended: `python inode_modbus.py`

    ---

    ! CAUTION: Docker uses the default 172.17.0.0 local network to assign IPs to containers that are launched. There may be errors when trying to communicate with ModBus devices if they are within a network with the same configuration
    To fix this we can tell the Docker daemon which network to use:

    `sudo nano /etc/docker/daemon.json`

    ``` json
    {
    "default-address-pools":
        [
            {
                "base":"172.20.0.0/16","size":24
            }
        ]
    }
    ```
    We must restart the Docker service for this change to take effect: `service docker restart`. 
    It has been indicated to use network 172.20.0.0 instead of 172.17.0.0, we can check with:

    ``` bash # We get a list with the IDs of the working containers
    sudo docker ps --format "table {{.ID}}\t{{.Status}}\t{{.Names}}"
    ```

    ``` bash # We consult the IP assigned to the container ID 
    sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' CONTAINER_ID
    Ex: > 172.20.0.2
    ```


2.  **Local**

    The only requirement to run it locally is to have Python3.9

    To run this service, the `CONFIG.json` file must be configured with an `operator_id` that exists in the database, so that the stored configuration can be loaded if it exists.

    * It is advisable to use a virtual environment to install the project dependencies. We create the environment with `python -m venv venv` and activate it:

        LINUX: `source venv/bin/activate`

        WINDOWS: `source venv/lib/activate.bat`

    * We install the dependencies of the requirements.txt file with pip:
    
        `pip install -r requirements.txt`

    * We run the project:

        `python inode_modbus.py`