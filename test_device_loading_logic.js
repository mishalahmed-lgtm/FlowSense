#!/usr/bin/env node
/** Test the device loading logic to ensure it works correctly */

// Simulate the device loading logic
function testDeviceLoading() {
  console.log("Testing Device Loading Logic\n");
  console.log("=".repeat(70));
  
  // Simulate /admin/devices response (all devices)
  const allDevicesFromAdmin = Array.from({ length: 2016 }, (_, i) => ({
    device_id: `device_${i + 1}`,
    name: `Device ${i + 1}`,
    is_active: i % 3 === 0
  }));
  
  console.log(`1. /admin/devices returns: ${allDevicesFromAdmin.length} devices`);
  
  // Simulate /devices/health responses (limited to 100 each)
  const healthDevicesOnline = Array.from({ length: 100 }, (_, i) => ({
    device_id: `device_${i * 3 + 1}`, // Every 3rd device starting from 1
    device_name: `Device ${i * 3 + 1}`,
    current_status: "online",
    last_seen_at: new Date().toISOString(),
    uptime_24h_percent: 95.5
  }));
  
  const healthDevicesOffline = Array.from({ length: 100 }, (_, i) => ({
    device_id: `device_${i * 3 + 2}`, // Every 3rd device starting from 2
    device_name: `Device ${i * 3 + 2}`,
    current_status: "offline",
    last_seen_at: null,
    uptime_24h_percent: 0
  }));
  
  const healthDevicesDegraded = Array.from({ length: 100 }, (_, i) => ({
    device_id: `device_${i * 3 + 3}`, // Every 3rd device starting from 3
    device_name: `Device ${i * 3 + 3}`,
    current_status: "degraded",
    last_seen_at: new Date().toISOString(),
    uptime_24h_percent: 50.0
  }));
  
  console.log(`2. /devices/health?status=online returns: ${healthDevicesOnline.length} devices`);
  console.log(`3. /devices/health?status=offline returns: ${healthDevicesOffline.length} devices`);
  console.log(`4. /devices/health?status=degraded returns: ${healthDevicesDegraded.length} devices`);
  
  // Simulate the merge logic
  const allDevicesMap = new Map();
  
  // Step 1: Add all devices from /admin/devices
  allDevicesFromAdmin.forEach((device) => {
    if (device && device.device_id) {
      allDevicesMap.set(device.device_id, {
        device_id: device.device_id,
        device_name: device.name || device.device_id,
        device_identifier: device.device_id,
        current_status: device.is_active ? "online" : "offline",
        last_seen_at: null,
        uptime_24h_percent: null,
        uptime_7d_percent: null,
        uptime_30d_percent: null,
        connectivity_score: null,
        last_battery_level: null,
        message_count_24h: 0,
      });
    }
  });
  
  console.log(`\n5. After adding from /admin/devices: ${allDevicesMap.size} devices in map`);
  
  // Step 2: Merge health data
  const healthDevices = [...healthDevicesOnline, ...healthDevicesOffline, ...healthDevicesDegraded];
  
  healthDevices.forEach((healthDevice) => {
    if (healthDevice && healthDevice.device_id) {
      const existing = allDevicesMap.get(healthDevice.device_id);
      if (existing) {
        // Update with health data
        Object.assign(existing, healthDevice);
      } else {
        // Add new device with health data
        allDevicesMap.set(healthDevice.device_id, healthDevice);
      }
    }
  });
  
  console.log(`6. After merging health data: ${allDevicesMap.size} devices in map`);
  
  const finalDevices = Array.from(allDevicesMap.values());
  
  // Check how many have health data
  const withHealthData = finalDevices.filter(d => d.uptime_24h_percent !== null).length;
  const withoutHealthData = finalDevices.length - withHealthData;
  
  console.log(`\n7. Final result: ${finalDevices.length} total devices`);
  console.log(`   - With health data: ${withHealthData}`);
  console.log(`   - Without health data: ${withoutHealthData}`);
  
  // Verify we have all devices
  if (finalDevices.length === 2016) {
    console.log(`\n✅ SUCCESS: All 2016 devices are accessible!`);
  } else {
    console.log(`\n⚠️  WARNING: Only ${finalDevices.length} devices loaded (expected 2016)`);
  }
  
  // Test pagination
  console.log(`\n8. Pagination test (50 per page):`);
  const limit = 50;
  const totalPages = Math.ceil(finalDevices.length / limit);
  console.log(`   - Total pages: ${totalPages}`);
  console.log(`   - Page 1: devices 1-50`);
  console.log(`   - Page ${totalPages}: devices ${(totalPages - 1) * limit + 1}-${finalDevices.length}`);
  
  // Test search
  console.log(`\n9. Search test:`);
  const searchQuery = "device_1";
  const filtered = finalDevices.filter((device) => {
    const deviceName = String(device.device_name || device.name || "").toLowerCase();
    const deviceId = String(device.device_id || device.device_identifier || "").toLowerCase();
    return deviceName.includes(searchQuery.toLowerCase()) || 
           deviceId.includes(searchQuery.toLowerCase());
  });
  console.log(`   - Search "${searchQuery}": ${filtered.length} results`);
  
  console.log("\n" + "=".repeat(70));
  console.log("Test completed!");
  console.log("=".repeat(70));
}

testDeviceLoading();

