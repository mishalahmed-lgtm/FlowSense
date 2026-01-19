/**
 * Dummy data generator for Firebase tenant (tenant_id = 2)
 * Generates realistic-looking data for health, environmental, energy dashboards, and alerts
 */

// Generate random number within range
const random = (min, max) => Math.random() * (max - min) + min;

// Generate random ID
const generateId = () => Math.random().toString(36).substring(2, 15);

// Generate time series data
const generateTimeSeries = (hours, valueMin, valueMax, trend = 'stable') => {
  const data = [];
  const now = new Date();
  let value = random(valueMin, valueMax);
  
  for (let i = hours; i >= 0; i--) {
    const timestamp = new Date(now - i * 60 * 60 * 1000);
    
    // Add trend
    if (trend === 'increasing') value += random(-2, 5);
    else if (trend === 'decreasing') value += random(-5, 2);
    else value += random(-3, 3);
    
    // Keep in bounds
    value = Math.max(valueMin, Math.min(valueMax, value));
    
    data.push({
      timestamp: timestamp.toISOString(),
      value: Math.round(value * 100) / 100,
    });
  }
  
  return data;
};

/**
 * Generate dummy health data for devices
 */
export function generateDummyHealthData(devices) {
  const totalDevices = devices.length;
  // Fixed distribution: 7064 online, 300 degraded, rest offline
  const onlineCount = 7064;
  const degradedCount = 300;
  
  return devices.map((device, index) => {
    // Preserve existing status if present (for SmartLPG tenant)
    const existingStatus = device.current_status || device.status;
    let status;
    if (existingStatus) {
      status = existingStatus; // Use existing status
    } else if (index < onlineCount) {
      status = 'online';
    } else if (index < onlineCount + degradedCount) {
      status = 'degraded';
    } else {
      status = 'offline';
    }
    
    const isOnline = status === 'online';
    const isDegraded = status === 'degraded';
    
    const uptime24h = isOnline ? random(85, 100) : isDegraded ? random(50, 85) : random(0, 50);
    const uptime7d = isOnline ? random(80, 98) : isDegraded ? random(45, 80) : random(0, 60);
    const uptime30d = isOnline ? random(75, 95) : isDegraded ? random(40, 75) : random(0, 70);
    const batteryLevel = isOnline ? Math.round(random(50, 100)) : isDegraded ? Math.round(random(20, 50)) : Math.round(random(5, 20));
    const lastSeenMinutes = isOnline ? random(0, 30) : isDegraded ? random(30, 120) : random(60, 1440);
    const lastSeenDate = new Date(Date.now() - lastSeenMinutes * 60 * 1000);
    
    // Generate battery history for last 7 days
    const batteryHistory = [];
    for (let i = 7; i >= 0; i--) {
      const timestamp = new Date(Date.now() - i * 24 * 60 * 60 * 1000);
      // Battery gradually decreases over time, with some variation
      const daysFactor = (7 - i) / 7; // 0 to 1
      const batteryValue = Math.max(20, batteryLevel + random(-5, 5) - (daysFactor * random(0, 20)));
      batteryHistory.push({
        timestamp: timestamp.toISOString(),
        battery: Math.round(batteryValue),
      });
    }
    
    // First seen is 30-90 days ago
    const firstSeenDaysAgo = Math.round(random(30, 90));
    const firstSeenDate = new Date(Date.now() - firstSeenDaysAgo * 24 * 60 * 60 * 1000);
    
    return {
      device_id: device.device_id || device.id,
      device_identifier: device.device_id || device.id,
      device_name: device.name || device.device_name || device.device_id,
      current_status: status,
      status: status, // Also set status field for compatibility
      last_seen_at: lastSeenDate.toISOString(),
      last_battery_level: batteryLevel,
      uptime_24h_percent: Math.round(uptime24h * 100) / 100,
      uptime_7d_percent: Math.round(uptime7d * 100) / 100,
      uptime_30d_percent: Math.round(uptime30d * 100) / 100,
      messages_24h: Math.round(random(100, 2000)),
      messages_7d: Math.round(random(1000, 15000)),
      messages_30d: Math.round(random(5000, 60000)),
      battery_history: generateTimeSeries(72, batteryLevel - 20, Math.min(100, batteryLevel + 10), 'decreasing')
        .map(point => ({
          timestamp: point.timestamp,
          battery_level: Math.round(point.value),
        })),
      connectivity_score: Math.round(uptime24h),
      signal_strength: Math.round(random(60, 100)),
    };
  });
}

/**
 * Generate dummy health summary
 */
export function generateDummyHealthSummary(healthDevices) {
  const totalDevices = healthDevices.length;
  // Check multiple status fields for compatibility
  const onlineDevices = healthDevices.filter(d => {
    const status = d.current_status || d.status || (d.is_active ? 'online' : 'offline');
    return status === 'online' || status === 'active';
  }).length;
  const degradedDevices = healthDevices.filter(d => {
    const status = d.current_status || d.status;
    return status === 'degraded';
  }).length;
  const offlineDevices = totalDevices - onlineDevices - degradedDevices;
  const lowBatteryDevices = healthDevices.filter(d => {
    const battery = d.last_battery_level || d.battery;
    return battery !== null && battery !== undefined && battery < 20;
  }).length;
  
  return {
    // Component expects these field names
    total_count: totalDevices,
    online_count: onlineDevices,
    offline_count: offlineDevices,
    unhealthy_count: degradedDevices,
    degraded_count: degradedDevices,
    // Also include backend format for compatibility
    total_devices: totalDevices,
    online_devices: onlineDevices,
    offline_devices: offlineDevices,
    degraded_devices: degradedDevices,
    unhealthy_devices: degradedDevices,
    low_battery_devices: lowBatteryDevices,
    critical_alerts: Math.round(random(0, 5)),
    warning_alerts: Math.round(random(2, 15)),
    avg_uptime_24h: Math.round(healthDevices.reduce((sum, d) => sum + d.uptime_24h_percent, 0) / totalDevices * 100) / 100,
    avg_uptime_7d: Math.round(healthDevices.reduce((sum, d) => sum + d.uptime_7d_percent, 0) / totalDevices * 100) / 100,
    avg_uptime_30d: Math.round(healthDevices.reduce((sum, d) => sum + d.uptime_30d_percent, 0) / totalDevices * 100) / 100,
  };
}

/**
 * Generate dummy environmental data
 */
export function generateDummyEnvironmentalData(devices, hours = 24) {
  // Calculate averages from device data
  const pm25Values = devices.map(() => random(5, 35));
  const pm10Values = devices.map(() => random(10, 80));
  const co2Values = devices.map(() => random(400, 1200));
  const tempValues = devices.map(() => random(18, 32));
  const humidityValues = devices.map(() => random(30, 70));
  const noiseValues = devices.map(() => random(35, 75));
  
  const avgPM25 = pm25Values.reduce((a, b) => a + b, 0) / pm25Values.length;
  const avgPM10 = pm10Values.reduce((a, b) => a + b, 0) / pm10Values.length;
  const avgCO2 = co2Values.reduce((a, b) => a + b, 0) / co2Values.length;
  const avgTemp = tempValues.reduce((a, b) => a + b, 0) / tempValues.length;
  const avgHumidity = humidityValues.reduce((a, b) => a + b, 0) / humidityValues.length;
  const avgNoise = noiseValues.reduce((a, b) => a + b, 0) / noiseValues.length;
  
  // Calculate AQI (simplified)
  const calculateAQI = (pm25, pm10) => {
    let aqi = 0;
    if (pm25 <= 12) aqi = Math.max(aqi, (pm25 / 12) * 50);
    else if (pm25 <= 35.4) aqi = Math.max(aqi, 50 + ((pm25 - 12) / 23.4) * 50);
    else aqi = Math.max(aqi, 100 + ((pm25 - 35.4) / 20) * 50);
    return Math.round(aqi);
  };
  
  const aqi = calculateAQI(avgPM25, avgPM10);
  
  // Format trends to match expected structure: {time: number, value: number}
  const formatTrends = (trendData) => {
    return trendData.map(point => ({
      time: new Date(point.timestamp).getTime(), // Convert ISO string to timestamp number
      value: point.value,
    })).sort((a, b) => a.time - b.time); // Sort by time ascending
  };
  
  return {
    summary: {
      pm25: Math.round(avgPM25 * 10) / 10,
      pm10: Math.round(avgPM10 * 10) / 10,
      co2: Math.round(avgCO2),
      aqi: aqi,
      temperature: Math.round(avgTemp * 10) / 10,
      humidity: Math.round(avgHumidity * 10) / 10,
      noise_level: Math.round(avgNoise * 10) / 10,
      active_sensors: devices.length,
    },
    trends: {
      pm25: formatTrends(generateTimeSeries(hours, avgPM25 - 10, avgPM25 + 10)),
      pm10: formatTrends(generateTimeSeries(hours, avgPM10 - 20, avgPM10 + 20)),
      co2: formatTrends(generateTimeSeries(hours, avgCO2 - 200, avgCO2 + 200)),
      temperature: formatTrends(generateTimeSeries(hours, avgTemp - 5, avgTemp + 5)),
      humidity: formatTrends(generateTimeSeries(hours, avgHumidity - 15, avgHumidity + 15)),
      noise: formatTrends(generateTimeSeries(hours, avgNoise - 15, avgNoise + 15)),
      aqi: formatTrends(generateTimeSeries(hours, Math.max(0, aqi - 30), aqi + 30)),
    },
    sensors: devices.map((device, idx) => ({
      device_id: device.device_id || device.id,
      device_name: device.name || device.device_name || device.device_id,
      pm25: Math.round(pm25Values[idx] * 10) / 10,
      pm10: Math.round(pm10Values[idx] * 10) / 10,
      co2: Math.round(co2Values[idx]),
      temperature: Math.round(tempValues[idx] * 10) / 10,
      humidity: Math.round(humidityValues[idx] * 10) / 10,
      noise_level: Math.round(noiseValues[idx] * 10) / 10,
      last_reading: new Date(Date.now() - random(0, 30) * 60 * 1000).toISOString(),
      status: Math.random() > 0.1 ? 'active' : 'inactive',
    })),
  };
}

/**
 * Generate dummy energy data
 */
export function generateDummyEnergyData(devices, hours = 24) {
  // Ensure devices array is valid
  if (!devices || !Array.isArray(devices) || devices.length === 0) {
    devices = Array.from({ length: 10 }, (_, i) => ({
      device_id: `device_${i + 1}`,
      name: `Device ${i + 1}`,
    }));
  }
  
  // Realistic consumption targets: 200/day, 2000/week, 4000/30days
  // FIXED TOTAL regardless of device count
  let baseTotalKWh;
  if (hours <= 24) {
    baseTotalKWh = 200; // ~200 units per day TOTAL
  } else if (hours <= 168) {
    baseTotalKWh = 2000; // ~2000 units per week TOTAL
  } else {
    baseTotalKWh = 4000; // ~4000 units per 30 days TOTAL
  }
  
  const costPerKWh = 0.5; // SAR per kWh
  const baseTotalCost = baseTotalKWh * costPerKWh;
  
  // Distribute consumption across devices proportionally (so total stays fixed)
  const avgConsumptionPerDevice = baseTotalKWh / Math.max(devices.length, 1);
  
  // Generate consumption per device (realistic small values that sum to baseTotalKWh)
  const deviceConsumption = [];
  let runningTotal = 0;
  
  devices.forEach((device, idx) => {
    let deviceKwh;
    if (idx === devices.length - 1) {
      // Last device: fill remainder to ensure exact total
      deviceKwh = Math.round((baseTotalKWh - runningTotal) * 100) / 100;
    } else {
      // Distribute proportionally with some randomness
      const remainingDevices = devices.length - idx;
      const avgRemaining = (baseTotalKWh - runningTotal) / remainingDevices;
      deviceKwh = Math.round(random(avgRemaining * 0.5, avgRemaining * 1.5) * 100) / 100;
      runningTotal += deviceKwh;
    }
    
    deviceConsumption.push({
      device_id: device.device_id || device.id || `device_${Math.random()}`,
      device_name: device.name || device.device_name || device.device_id || `Device ${Math.random()}`,
      total_kwh: deviceKwh,
      cost: Math.round(deviceKwh * costPerKWh * 100) / 100,
      avg_power_w: Math.round((deviceKwh / hours) * 1000), // Convert kWh to watts
      peak_power_w: Math.round((deviceKwh / hours) * 1000 * 1.5),
      energy_efficiency: Math.round(random(70, 90)),
      utility_kind: ['electricity', 'gas', 'water'][Math.floor(Math.random() * 3)],
    });
  });
  
  // Use fixed totals (already ensured by last device calculation)
  const totalKWh = baseTotalKWh;
  const totalCost = baseTotalCost;
  const avgPower = Math.round(deviceConsumption.reduce((sum, d) => sum + d.avg_power_w, 0) / devices.length);
  
  // Generate trends based on time range (24h=hourly, 7d/30d=daily)
  const trendData = [];
  const numPoints = hours <= 24 ? hours : (hours <= 168 ? 7 : 30); // 24 points for 24h, 7 for 7d, 30 for 30d
  const intervalHours = hours <= 24 ? 1 : (hours / numPoints);
  
  for (let i = numPoints; i >= 0; i--) {
    const timestamp = new Date(Date.now() - i * intervalHours * 60 * 60 * 1000);
    const hour = timestamp.getHours();
    const dayOfWeek = timestamp.getDay(); // 0=Sunday, 6=Saturday
    
    // Simulate daily pattern (higher during day, lower at night)
    const dayFactor = hour >= 6 && hour <= 22 ? 1.2 : 0.7;
    // Simulate weekly pattern (lower on weekends)
    const weekFactor = (dayOfWeek === 0 || dayOfWeek === 6) ? 0.8 : 1.0;
    const randomFactor = random(0.8, 1.2);
    
    const consumption = (totalKWh / numPoints) * dayFactor * weekFactor * randomFactor;
    const costPerPoint = (totalCost / numPoints) * dayFactor * weekFactor * randomFactor;
    
    trendData.push({
      timestamp: timestamp.toISOString(),
      hour: hours <= 24 ? `${hour}:00` : timestamp.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      date: timestamp.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      electricity_kwh: Math.round(consumption * 0.6 * 100) / 100,
      gas_kwh: Math.round(consumption * 0.25 * 100) / 100,
      water_liters: Math.round(consumption * 50),
      cost: Math.round(costPerPoint * 100) / 100,
    });
  }
  
  return {
    summary: {
      total_consumption_kwh: Math.round(totalKWh * 100) / 100,
      total_cost: Math.round(totalCost * 100) / 100,
      avg_power_w: avgPower,
      peak_demand_w: Math.round(avgPower * 1.5),
      cost_per_kwh: Math.round((totalCost / totalKWh) * 100) / 100,
      active_meters: devices.length,
    },
    trends: trendData,
    topConsumers: deviceConsumption
      .sort((a, b) => b.total_kwh - a.total_kwh)
      .slice(0, 10)
      .map(device => ({
        device_id: device.device_id,
        device_name: device.device_name,
        utility_kind: device.utility_kind,
        consumption: device.total_kwh, // Map total_kwh to consumption
        cost: device.cost,
        currency: "SAR", // Add currency field
      })),
    breakdown: [
      { name: 'Electricity', value: Math.round(totalKWh * 0.6), color: '#facc15' },
      { name: 'Gas', value: Math.round(totalKWh * 0.25), color: '#f97316' },
      { name: 'Water', value: Math.round(totalKWh * 0.15), color: '#3b82f6' },
    ],
    costBreakdown: [
      { name: 'Electricity', value: Math.round(totalCost * 0.65 * 100) / 100, color: '#facc15' },
      { name: 'Gas', value: Math.round(totalCost * 0.20 * 100) / 100, color: '#f97316' },
      { name: 'Water', value: Math.round(totalCost * 0.15 * 100) / 100, color: '#3b82f6' },
    ],
  };
}

/**
 * Generate dummy alerts for devices
 */
export function generateDummyAlerts(devices, count = 15) {
  const alertTypes = [
    { title: 'High Temperature Alert', message: 'Temperature exceeded threshold', priority: 'high', field: 'temperature' },
    { title: 'Low Battery Warning', message: 'Device battery is running low', priority: 'medium', field: 'battery' },
    { title: 'Connection Lost', message: 'Device has lost connection', priority: 'critical', field: 'connectivity' },
    { title: 'Sensor Malfunction', message: 'Sensor readings are abnormal', priority: 'high', field: 'sensor' },
    { title: 'High Humidity', message: 'Humidity levels are above normal', priority: 'medium', field: 'humidity' },
    { title: 'Poor Air Quality', message: 'PM2.5 levels are high', priority: 'high', field: 'pm25' },
    { title: 'Noise Level Warning', message: 'Noise levels exceeded threshold', priority: 'medium', field: 'noise' },
    { title: 'Power Consumption Spike', message: 'Unusual power consumption detected', priority: 'medium', field: 'power' },
  ];
  
  const statuses = ['open', 'acknowledged', 'resolved', 'closed'];
  const alerts = [];
  
  for (let i = 0; i < count; i++) {
    const device = devices[Math.floor(Math.random() * devices.length)];
    const alertType = alertTypes[Math.floor(Math.random() * alertTypes.length)];
    const status = statuses[Math.floor(Math.random() * statuses.length)];
    const createdMinutesAgo = random(0, 4320); // Up to 3 days ago
    const createdAt = new Date(Date.now() - createdMinutesAgo * 60 * 1000);
    
    alerts.push({
      id: generateId(),
      tenant_id: 2,
      device_id: device.device_id || device.id,
      device_name: device.name || device.device_name || device.device_id,
      rule_id: generateId(),
      rule_name: alertType.title,
      priority: alertType.priority,
      status: status,
      title: alertType.title,
      message: `${alertType.message} for device ${device.name || device.device_id}`,
      trigger_data: {
        field: alertType.field,
        value: Math.round(random(50, 100)),
        threshold: Math.round(random(40, 60)),
        operator: '>',
      },
      created_at: createdAt.toISOString(),
      updated_at: createdAt.toISOString(),
      acknowledged_at: status !== 'open' ? new Date(createdAt.getTime() + random(5, 60) * 60 * 1000).toISOString() : null,
      resolved_at: (status === 'resolved' || status === 'closed') ? new Date(createdAt.getTime() + random(60, 180) * 60 * 1000).toISOString() : null,
    });
  }
  
  return alerts.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
}

/**
 * Generate SmartLPG-specific alerts for degraded devices and low gas levels
 */
export function generateSmartLPGAlerts(devices, tekelekDevices = []) {
  const alerts = [];
  
  // 1. Generate alerts for degraded devices (all of them)
  const degradedDevices = devices.filter(d => d.current_status === 'degraded' || d.status === 'degraded');
  // Generate alerts for all degraded devices (not just a subset)
  degradedDevices.forEach((device, idx) => {
    const createdMinutesAgo = random(0, 1440); // Up to 24 hours ago
    const createdAt = new Date(Date.now() - createdMinutesAgo * 60 * 1000);
    
    alerts.push({
      id: generateId(),
      tenant_id: 3,
      device_id: device.device_id || device.id,
      device_name: device.name || device.device_name || device.device_id,
      rule_id: generateId(),
      rule_name: 'Device Degraded',
      priority: 'high',
      status: 'open',
      title: 'Device Performance Degraded',
      message: `Device ${device.name || device.device_id} is experiencing degraded performance. Please investigate.`,
      trigger_data: {
        field: 'status',
        value: 'degraded',
        threshold: 'online',
        operator: '!=',
      },
      created_at: createdAt.toISOString(),
      updated_at: createdAt.toISOString(),
      acknowledged_at: null,
      resolved_at: null,
    });
  });
  
  // 2. Generate critical alerts for low gas levels (<30%)
  const lowGasDevices = tekelekDevices.filter(device => {
    const levelPercent = device.telemetry?.data?.level_percent || device.level_percent || 100;
    return levelPercent < 30;
  });
  
  lowGasDevices.forEach((device, idx) => {
    const levelPercent = device.telemetry?.data?.level_percent || device.level_percent || 0;
    const createdMinutesAgo = random(0, 720); // Up to 12 hours ago
    const createdAt = new Date(Date.now() - createdMinutesAgo * 60 * 1000);
    
    alerts.push({
      id: generateId(),
      tenant_id: 3,
      device_id: device.device_id || device.id,
      device_name: device.name || device.device_name || device.device_id,
      rule_id: generateId(),
      rule_name: 'Low Gas Level Alert',
      priority: 'critical',
      status: 'open',
      title: 'Gas Tank Low - Refill Required',
      message: `Gas level is at ${levelPercent.toFixed(1)}% for device ${device.name || device.device_id}. Please schedule refill.`,
      trigger_data: {
        field: 'level_percent',
        value: levelPercent,
        threshold: 30,
        operator: '<',
      },
      created_at: createdAt.toISOString(),
      updated_at: createdAt.toISOString(),
      acknowledged_at: null,
      resolved_at: null,
    });
  });
  
  // 3. Add some offline device alerts (more than before)
  const offlineDevices = devices.filter(d => d.current_status === 'offline' || d.status === 'offline');
  offlineDevices.slice(0, Math.min(15, offlineDevices.length)).forEach((device) => {
    const createdMinutesAgo = random(60, 2880); // 1 hour to 2 days ago
    const createdAt = new Date(Date.now() - createdMinutesAgo * 60 * 1000);
    
    alerts.push({
      id: generateId(),
      tenant_id: 3,
      device_id: device.device_id || device.id,
      device_name: device.name || device.device_name || device.device_id,
      rule_id: generateId(),
      rule_name: 'Device Offline',
      priority: 'critical',
      status: 'open',
      title: 'Device Offline',
      message: `Device ${device.name || device.device_id} has been offline for ${Math.floor(createdMinutesAgo / 60)} hours.`,
      trigger_data: {
        field: 'status',
        value: 'offline',
        threshold: 'online',
        operator: '!=',
      },
      created_at: createdAt.toISOString(),
      updated_at: createdAt.toISOString(),
      acknowledged_at: null,
      resolved_at: null,
    });
  });
  
  return alerts.sort((a, b) => {
    // Sort by priority first (critical > high > medium), then by date
    const priorityOrder = { critical: 3, high: 2, medium: 1, low: 0 };
    const priorityDiff = (priorityOrder[b.priority] || 0) - (priorityOrder[a.priority] || 0);
    if (priorityDiff !== 0) return priorityDiff;
    return new Date(b.created_at) - new Date(a.created_at);
  });
}
