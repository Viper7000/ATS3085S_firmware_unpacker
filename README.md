## 1. ATS3085S Smartwatch Firmware Unpacker

___Usage:___ python firmware_unpacker.py <firmware_file_name.fw>

___Example:___ python firmware_unpacker.py A5S16GLY_C229G_D2-2026-02-03-17-32_V1_72_86_debug.fw

## 2. ATS3085S Smartwatch UI Resource Unpacker. The other_res file. Requires the lz4 package.
This file will be in the unpacked firmware folder if the firmware contains resources (debug version).

___Simply run other_res_unpacker.py in the other_res folder.___

## 3. Main firmware Unpacker. A sample upgrade.fw file unpacker. This file will be in the unpacked firmware folder.

___Simply run upgradefw_unpacker.py in the upgrade.fw folder.___

## Description of the file structure in Russian. You can use a translator :)

[Firmware header rus](Firmware_header_rus.md)

[Other_res header rus](Other_res_header_rus.md)

[Upgradefw header rus](Upgradefw_header_rus.md)
