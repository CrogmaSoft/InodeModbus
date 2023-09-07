# INODE MODBUS Deployment

To launch new INODE MODBUS services we will use "image-derivation". For each new service, we will create new images with the desired configuration. We can use the example `test_plc1` as a reference and create an image that has the base name identical to the original `inodemodbuspython` despite having the operator label set to `"test_plc1"`:

* First create a new folder called `operators/` and inside it another new folder for each new operator, such as `operators/test_plc1` .
* Within the new operator folder we can copy the contents of the example `template` and configure the `"operator_id"` from the CONFIG.json file to match the one recorded in the MongoDB database, where the configuration of each new `operator should be set.

## AUTOMATIC MODE
After configuring each `operator` in MongoDB and creating the folders inside `operators/` with the CONFIG.json for each one, we can launch the script `deploy.sh` to stop the old containers, generate the images and launch the new containers. It is possible to indicate to the script the name of one of the containers that we want to deploy, so that it performs the whole process only for this. 

## MANUAL MODE
We can generate the new image that will take as base the existing configuration in its same directory:
`docker build -t inodemodbuspython:test_plc1 . `

We then configure the unattended execution as indicated in the documentation: `docker run -d --restart always inodemodbuspython:test_plc1`