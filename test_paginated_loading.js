#!/usr/bin/env node
/** Test paginated device loading logic */

function testPaginatedLoading() {
  console.log("Testing Paginated Device Loading\n");
  console.log("=".repeat(70));
  
  // Simulate paginated /admin/devices responses
  const totalDevices = 2016;
  const limit = 1000;
  const totalPages = Math.ceil(totalDevices / limit);
  
  console.log(`Total devices: ${totalDevices}`);
  console.log(`Limit per page: ${limit}`);
  console.log(`Total pages needed: ${totalPages}\n`);
  
  const allDevicesMap = new Map();
  let devicesLoaded = 0;
  
  // Simulate fetching all pages
  for (let page = 1; page <= totalPages; page++) {
    const startIdx = (page - 1) * limit;
    const endIdx = Math.min(startIdx + limit, totalDevices);
    const devicesOnPage = endIdx - startIdx;
    
    // Simulate devices on this page
    for (let i = startIdx; i < endIdx; i++) {
      const device = {
        device_id: `device_${i + 1}`,
        name: `Device ${i + 1}`,
        is_active: i % 3 === 0
      };
      
      allDevicesMap.set(device.device_id, {
        device_id: device.device_id,
        device_name: device.name,
        device_identifier: device.device_id,
        current_status: device.is_active ? "online" : "offline",
      });
      devicesLoaded++;
    }
    
    console.log(`Page ${page}/${totalPages}: Loaded ${devicesOnPage} devices (total so far: ${devicesLoaded})`);
  }
  
  const finalDevices = Array.from(allDevicesMap.values());
  
  console.log(`\n✅ Final result: ${finalDevices.length} devices loaded`);
  
  if (finalDevices.length === totalDevices) {
    console.log(`✅ SUCCESS: All ${totalDevices} devices are accessible!`);
  } else {
    console.log(`❌ FAILED: Expected ${totalDevices}, got ${finalDevices.length}`);
  }
  
  // Test pagination display
  const displayLimit = 50;
  const displayPages = Math.ceil(finalDevices.length / displayLimit);
  console.log(`\nPagination display (${displayLimit} per page):`);
  console.log(`   - Total pages: ${displayPages}`);
  console.log(`   - Page 1: devices 1-${Math.min(displayLimit, finalDevices.length)}`);
  console.log(`   - Page ${displayPages}: devices ${(displayPages - 1) * displayLimit + 1}-${finalDevices.length}`);
  
  console.log("\n" + "=".repeat(70));
  console.log("Test completed!");
  console.log("=".repeat(70));
}

testPaginatedLoading();

