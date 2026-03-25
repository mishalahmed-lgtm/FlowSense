/**
 * Dev/demo seed helpers for SmartLPG (Firebase).
 * Used by FOTAJobsPage "Seed Sample Firmware Versions" for tenant admins.
 */

import { saveFirmwareVersionToFirebase } from "../services/smartLPGFirebaseService.js";

const SAMPLE_FIRMWARE = [
  {
    device_type: "Tekelek Ultrasonic",
    name: "Tekelek Tank Sensor",
    version: "2.4.1",
    file_path: "firmware/tekelek/tekelek-2.4.1.bin",
    checksum: "sha256:demo0001",
    file_size_bytes: 245760,
    release_notes: "Demo seed — stability improvements.",
    min_hw_version: "1.0",
    is_recommended: true,
    is_mandatory: false,
    tenant_id: 3,
  },
  {
    device_type: "ASCO Valve",
    name: "ASCO Valve Controller",
    version: "1.8.0",
    file_path: "firmware/asco/asco-1.8.0.bin",
    checksum: "sha256:demo0002",
    file_size_bytes: 189440,
    release_notes: "Demo seed — valve timing fixes.",
    min_hw_version: null,
    is_recommended: false,
    is_mandatory: false,
    tenant_id: 3,
  },
  {
    device_type: "Teltonika Gateway",
    name: "Teltonika Gateway",
    version: "7.12.3",
    file_path: "firmware/teltonika/gw-7.12.3.bin",
    checksum: "sha256:demo0003",
    file_size_bytes: 5242880,
    release_notes: "Demo seed — NB-IoT stack update.",
    min_hw_version: "2.0",
    is_recommended: false,
    is_mandatory: false,
    tenant_id: 3,
  },
];

/**
 * Insert sample firmware version documents into `smartLPG_firmware_versions`.
 */
export async function seedFirmwareVersions() {
  for (const row of SAMPLE_FIRMWARE) {
    await saveFirmwareVersionToFirebase(row);
  }
}
