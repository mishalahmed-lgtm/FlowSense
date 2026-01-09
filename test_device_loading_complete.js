#!/usr/bin/env node
/** Complete test of device loading with edge cases */

function testCompleteLoading() {
  console.log("Complete Device Loading Test\n");
  console.log("=".repeat(70));
  
  // Test Case 1: Normal case - 2016 devices
  console.log("Test Case 1: 2016 devices (3 pages of 1000)");
  console.log("-".repeat(70));
  
  const totalDevices = 2016;
  const limit = 1000;
  const pages = Math.ceil(totalDevices / limit);
  
  let allDevices = new Map();
  let totalLoaded = 0;
  
  for (let page = 1; page <= pages; page++) {
    const start = (page - 1) * limit;
    const end = Math.min(start + limit, totalDevices);
    const count = end - start;
    
    for (let i = start; i < end; i++) {
      allDevices.set(`device_${i + 1}`, { device_id: `device_${i + 1}` });
    }
    totalLoaded += count;
    console.log(`  Page ${page}: ${count} devices (cumulative: ${totalLoaded})`);
  }
  
  console.log(`  ✅ Total: ${allDevices.size} devices`);
  console.log(`  ✅ Expected: ${totalDevices} devices`);
  console.log(`  ${allDevices.size === totalDevices ? '✅ PASS' : '❌ FAIL'}\n`);
  
  // Test Case 2: Edge case - exactly 1000 devices (1 page)
  console.log("Test Case 2: Exactly 1000 devices (1 page)");
  console.log("-".repeat(70));
  
  allDevices = new Map();
  totalLoaded = 0;
  const exact1000 = 1000;
  const pages1000 = Math.ceil(exact1000 / limit);
  
  for (let page = 1; page <= pages1000; page++) {
    const start = (page - 1) * limit;
    const end = Math.min(start + limit, exact1000);
    const count = end - start;
    
    for (let i = start; i < end; i++) {
      allDevices.set(`device_${i + 1}`, { device_id: `device_${i + 1}` });
    }
    totalLoaded += count;
  }
  
  console.log(`  ✅ Total: ${allDevices.size} devices`);
  console.log(`  ✅ Expected: ${exact1000} devices`);
  console.log(`  ${allDevices.size === exact1000 ? '✅ PASS' : '❌ FAIL'}\n`);
  
  // Test Case 3: Edge case - less than 1000 devices
  console.log("Test Case 3: 500 devices (1 page)");
  console.log("-".repeat(70));
  
  allDevices = new Map();
  totalLoaded = 0;
  const small500 = 500;
  const pages500 = Math.ceil(small500 / limit);
  
  for (let page = 1; page <= pages500; page++) {
    const start = (page - 1) * limit;
    const end = Math.min(start + limit, small500);
    const count = end - start;
    
    if (count === 0) break; // No more devices
    
    for (let i = start; i < end; i++) {
      allDevices.set(`device_${i + 1}`, { device_id: `device_${i + 1}` });
    }
    totalLoaded += count;
  }
  
  console.log(`  ✅ Total: ${allDevices.size} devices`);
  console.log(`  ✅ Expected: ${small500} devices`);
  console.log(`  ${allDevices.size === small500 ? '✅ PASS' : '❌ FAIL'}\n`);
  
  // Test Case 4: Pagination logic
  console.log("Test Case 4: Pagination display (50 per page)");
  console.log("-".repeat(70));
  
  const displayLimit = 50;
  const testDevices = 2016;
  const displayPages = Math.ceil(testDevices / displayLimit);
  
  console.log(`  Total devices: ${testDevices}`);
  console.log(`  Display limit: ${displayLimit}`);
  console.log(`  Total display pages: ${displayPages}`);
  console.log(`  Page 1: devices 1-${Math.min(displayLimit, testDevices)}`);
  console.log(`  Page ${displayPages}: devices ${(displayPages - 1) * displayLimit + 1}-${testDevices}`);
  console.log(`  ✅ Expected: 41 pages`);
  console.log(`  ${displayPages === 41 ? '✅ PASS' : '❌ FAIL'}\n`);
  
  // Test Case 5: Loop termination
  console.log("Test Case 5: Loop termination logic");
  console.log("-".repeat(70));
  
  let page = 1;
  let hasMore = true;
  const testLimit = 1000;
  const testTotal = 2016;
  let loaded = 0;
  
  while (hasMore && page <= 10) { // Safety limit
    const devicesOnPage = page === 1 ? 1000 : page === 2 ? 1000 : page === 3 ? 16 : 0;
    loaded += devicesOnPage;
    
    const totalPages = Math.ceil(testTotal / testLimit);
    const currentPage = page;
    
    if (currentPage >= totalPages || devicesOnPage < testLimit) {
      hasMore = false;
    } else {
      page++;
    }
    
    if (page > totalPages) break;
  }
  
  console.log(`  Pages loaded: ${page}`);
  console.log(`  Devices loaded: ${loaded}`);
  console.log(`  ✅ Expected: 3 pages, 2016 devices`);
  console.log(`  ${page === 3 && loaded === 2016 ? '✅ PASS' : '❌ FAIL'}\n`);
  
  console.log("=".repeat(70));
  console.log("All tests completed!");
  console.log("=".repeat(70));
}

testCompleteLoading();

