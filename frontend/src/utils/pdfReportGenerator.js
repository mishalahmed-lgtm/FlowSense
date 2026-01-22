/**
 * PDF Report Generator for SmartLPG Utility Billing
 * Generates professional PDF reports using browser's print functionality
 */

/**
 * Get company details from localStorage or use defaults
 */
export function getCompanyDetails() {
  const saved = localStorage.getItem('smartlpg_company_details');
  if (saved) {
    try {
      return JSON.parse(saved);
    } catch (e) {
      console.error('Error parsing company details:', e);
    }
  }
  
  // Default company details
  return {
    companyName: 'SmartLPG Solutions',
    address: 'Dubai Silicon Oasis, Dubai, UAE',
    phone: '+971 4 XXX XXXX',
    email: 'billing@smartlpg.ae',
    taxId: 'TRN: 100000000000003',
    logo: null, // Base64 encoded image or null (optional)
    headerText: '', // Header text for reports (required)
    footerText: '' // Footer text for reports (required)
  };
}

/**
 * Save company details to localStorage
 */
export function saveCompanyDetails(details) {
  localStorage.setItem('smartlpg_company_details', JSON.stringify(details));
}

/**
 * Generate HTML for the billing report
 */
function generateReportHTML(reportData, companyDetails) {
  const {
    reportTitle,
    periodStart,
    periodEnd,
    devices,
    summary,
    reportType = 'per-device' // 'per-device' or 'consolidated'
  } = reportData;
  
  const formatCurrency = (amount) => `${summary.currency || 'AED'} ${parseFloat(amount).toFixed(2)}`;
  const formatDate = (dateStr) => new Date(dateStr).toLocaleDateString('en-US', { 
    year: 'numeric', 
    month: 'long', 
    day: 'numeric' 
  });
  
  let logoHTML = '';
  if (companyDetails.logo) {
    logoHTML = `<img src="${companyDetails.logo}" alt="Company Logo" style="max-width: 150px; max-height: 80px; margin-bottom: 10px;" />`;
  }
  
  // Generate device rows
  let deviceRowsHTML = '';
  if (reportType === 'per-device' && devices && devices.length > 0) {
    deviceRowsHTML = devices.map((device, index) => `
      <tr style="${index % 2 === 0 ? 'background-color: #f9f9f9;' : ''}">
        <td style="padding: 14px 16px; border-bottom: 1px solid #e0e0e0;">${index + 1}</td>
        <td style="padding: 14px 16px; border-bottom: 1px solid #e0e0e0;">
          <strong>${device.device_name || device.device_id}</strong><br/>
          <small style="color: #666;">${device.device_id}</small>
        </td>
        <td style="padding: 14px 16px; border-bottom: 1px solid #e0e0e0; text-align: center;">
          ${device.tank_capacity || '1,000'} L
        </td>
        <td style="padding: 14px 16px; border-bottom: 1px solid #e0e0e0; text-align: center;">
          ${device.current_level_percent || '0'}%
        </td>
        <td style="padding: 14px 16px; border-bottom: 1px solid #e0e0e0; text-align: right;">
          ${device.consumption ? parseFloat(device.consumption).toFixed(2) : '0.00'} L
        </td>
        <td style="padding: 14px 16px; border-bottom: 1px solid #e0e0e0; text-align: right;">
          ${formatCurrency(device.cost || 0)}
        </td>
      </tr>
    `).join('');
  }
  
  return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>${reportTitle}</title>
  <style>
    @media print {
      body { margin: 0; padding: 30px 40px; }
      .no-print { display: none !important; }
      @page { margin: 1cm; size: landscape; }
    }
    
    body {
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      color: #333;
      line-height: 1.6;
      max-width: 280mm;
      margin: 0 auto;
      padding: 30px 40px;
      background: white;
    }
    
    .header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 40px;
      padding-bottom: 20px;
      border-bottom: 3px solid #3b82f6;
    }
    
    .company-info {
      flex: 1;
    }
    
    .company-name {
      font-size: 24px;
      font-weight: bold;
      color: #3b82f6;
      margin-bottom: 10px;
    }
    
    .company-details {
      font-size: 12px;
      color: #666;
      line-height: 1.8;
    }
    
    .report-info {
      text-align: right;
      flex: 1;
    }
    
    .report-title {
      font-size: 28px;
      font-weight: bold;
      color: #1f2937;
      margin-bottom: 10px;
    }
    
    .report-period {
      font-size: 14px;
      color: #666;
      margin-bottom: 5px;
    }
    
    .report-date {
      font-size: 12px;
      color: #999;
    }
    
    .summary-section {
      background: linear-gradient(135deg, #fff5f0 0%, #ffe6d9 100%);
      padding: 25px;
      border-radius: 8px;
      margin-bottom: 30px;
      border-left: 4px solid #3b82f6;
    }
    
    .summary-title {
      font-size: 18px;
      font-weight: bold;
      color: #1f2937;
      margin-bottom: 15px;
    }
    
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 20px;
    }
    
    .summary-item {
      text-align: center;
    }
    
    .summary-label {
      font-size: 12px;
      color: #666;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 5px;
    }
    
    .summary-value {
      font-size: 24px;
      font-weight: bold;
      color: #1f2937;
    }
    
    .summary-value.highlight {
      color: #3b82f6;
    }
    
    .details-section {
      margin-bottom: 30px;
    }
    
    .section-title {
      font-size: 18px;
      font-weight: bold;
      color: #1f2937;
      margin-bottom: 15px;
      padding-bottom: 8px;
      border-bottom: 2px solid #e5e7eb;
    }
    
    table {
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 20px;
      background: white;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      border-radius: 8px;
      overflow: hidden;
    }
    
    thead {
      background: #3b82f6;
      color: white;
    }
    
    th {
      padding: 16px 16px;
      text-align: left;
      font-weight: 600;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    
    th.text-center {
      text-align: center;
    }
    
    th.text-right {
      text-align: right;
    }
    
    .footer {
      margin-top: 50px;
      padding-top: 20px;
      border-top: 2px solid #e5e7eb;
      font-size: 11px;
      color: #666;
      text-align: center;
    }
    
    .notes {
      background: #f9fafb;
      padding: 15px;
      border-radius: 6px;
      margin-top: 20px;
      font-size: 12px;
      color: #666;
    }
    
    .notes strong {
      color: #1f2937;
      display: block;
      margin-bottom: 5px;
    }
    
    .print-button {
      position: fixed;
      top: 20px;
      right: 20px;
      background: #3b82f6;
      color: white;
      border: none;
      padding: 12px 24px;
      border-radius: 6px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 4px 6px rgba(0,0,0,0.1);
      z-index: 1000;
    }
    
    .print-button:hover {
      background: #2563eb;
    }
  </style>
</head>
<body>
  <button class="print-button no-print" onclick="window.print()">🖨️ Print / Save as PDF</button>
  
  <div class="header">
    ${companyDetails.headerText ? `<div style="margin-bottom: 20px; padding: 15px; background: #eff6ff; border-left: 4px solid #3b82f6; border-radius: 4px; font-size: 14px; color: #1e40af; line-height: 1.6;">${companyDetails.headerText}</div>` : ''}
    <div class="company-info">
      ${logoHTML}
      <div class="company-name">${companyDetails.companyName}</div>
      <div class="company-details">
        ${companyDetails.address}<br/>
        Phone: ${companyDetails.phone}<br/>
        Email: ${companyDetails.email}<br/>
        ${companyDetails.taxId}
      </div>
    </div>
    <div class="report-info">
      <div class="report-title">${reportTitle}</div>
      <div class="report-period">
        <strong>Period:</strong> ${formatDate(periodStart)} - ${formatDate(periodEnd)}
      </div>
      <div class="report-date">
        Generated: ${formatDate(new Date())}
      </div>
    </div>
  </div>
  
  <div class="summary-section">
    <div class="summary-title">📊 Report Summary</div>
    <div class="summary-grid">
      <div class="summary-item">
        <div class="summary-label">Total Devices</div>
        <div class="summary-value">${summary.totalDevices || 0}</div>
      </div>
      <div class="summary-item">
        <div class="summary-label">Total Consumption</div>
        <div class="summary-value">${parseFloat(summary.totalConsumption || 0).toFixed(2)} L</div>
      </div>
      <div class="summary-item">
        <div class="summary-label">Cost Per Litre</div>
        <div class="summary-value">${formatCurrency(summary.costPerLitre || 3)}</div>
      </div>
      <div class="summary-item">
        <div class="summary-label">Total Amount</div>
        <div class="summary-value highlight">${formatCurrency(summary.totalAmount || 0)}</div>
      </div>
    </div>
  </div>
  
  ${reportType === 'per-device' && devices && devices.length > 0 ? `
    <div class="details-section">
      <div class="section-title">📋 Device Consumption Details</div>
      <table>
        <thead>
          <tr>
            <th style="width: 5%;">#</th>
            <th style="width: 30%;">Device</th>
            <th class="text-center" style="width: 15%;">Tank Capacity</th>
            <th class="text-center" style="width: 15%;">Current Level</th>
            <th class="text-right" style="width: 17.5%;">Consumption (L)</th>
            <th class="text-right" style="width: 17.5%;">Amount</th>
          </tr>
        </thead>
        <tbody>
          ${deviceRowsHTML}
        </tbody>
        <tfoot style="background: #f3f4f6; font-weight: bold;">
          <tr>
            <td colspan="4" style="padding: 18px 16px; text-align: right; border-top: 2px solid #d1d5db;">
              <strong>TOTAL:</strong>
            </td>
            <td style="padding: 18px 16px; text-align: right; border-top: 2px solid #d1d5db;">
              ${parseFloat(summary.totalConsumption || 0).toFixed(2)} L
            </td>
            <td style="padding: 18px 16px; text-align: right; border-top: 2px solid #d1d5db; color: #3b82f6;">
              ${formatCurrency(summary.totalAmount || 0)}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  ` : ''}
  
  <div class="notes">
    <strong>Notes:</strong>
    • Each ultrasonic sensor monitors a 1,000 litre LPG tank<br/>
    • Billing rate: ${formatCurrency(summary.costPerLitre || 3)} per litre<br/>
    • Consumption calculated as: (100% - Current Level %) × Tank Capacity<br/>
    • All amounts are in ${summary.currency || 'AED'} (UAE Dirham)<br/>
    • This report is automatically generated based on real-time sensor data
  </div>
  
  <div class="footer">
    ${companyDetails.footerText ? `<div style="margin-bottom: 15px; padding: 15px; background: #eff6ff; border-left: 4px solid #3b82f6; border-radius: 4px; font-size: 13px; color: #1e40af; line-height: 1.6;">${companyDetails.footerText}</div>` : ''}
    <p>
      <strong>${companyDetails.companyName}</strong><br/>
      ${companyDetails.address} | ${companyDetails.phone} | ${companyDetails.email}
    </p>
    <p style="margin-top: 10px; font-size: 10px; color: #999;">
      This is a computer-generated document. No signature is required.
    </p>
  </div>
</body>
</html>
  `.trim();
}

/**
 * Generate and open PDF report in new window
 */
export function generateBillingReport(reportData, companyDetails = null) {
  const company = companyDetails || getCompanyDetails();
  const html = generateReportHTML(reportData, company);
  
  // Open in new window
  const printWindow = window.open('', '_blank', 'width=1000,height=800');
  if (printWindow) {
    printWindow.document.write(html);
    printWindow.document.close();
    
    // Auto-trigger print dialog after content loads
    printWindow.onload = () => {
      setTimeout(() => {
        printWindow.focus();
        // Don't auto-print, let user decide
        // printWindow.print();
      }, 250);
    };
  } else {
    alert('Please allow pop-ups to generate the report');
  }
}

/**
 * Prepare report data from SmartLPG devices for per-device report
 */
export function preparePerDeviceReportData(devices, fromDate, toDate) {
  const deviceReports = devices.map(device => {
    const consumption = parseFloat(device.consumption || 0);
    const cost = parseFloat(device.amount || device.cost || 0);
    
    return {
      device_id: device.device_id,
      device_name: device.device_name || device.name || device.device_id,
      tank_capacity: '1,000',
      current_level_percent: device.current_level_percent || 0,
      consumption: consumption.toFixed(2),
      cost: cost.toFixed(2)
    };
  });
  
  const totalConsumption = devices.reduce((sum, d) => sum + parseFloat(d.consumption || 0), 0);
  const totalAmount = devices.reduce((sum, d) => sum + parseFloat(d.amount || d.cost || 0), 0);
  
  return {
    reportTitle: 'LPG Consumption Billing Report',
    periodStart: fromDate,
    periodEnd: toDate,
    devices: deviceReports,
    reportType: 'per-device',
    summary: {
      totalDevices: devices.length,
      totalConsumption: totalConsumption,
      costPerLitre: 3,
      totalAmount: totalAmount,
      currency: 'AED'
    }
  };
}

/**
 * Prepare report data for consolidated report
 */
export function prepareConsolidatedReportData(consolidatedData, fromDate, toDate) {
  const gasData = consolidatedData.find(d => d.utility_kind === 'gas') || {};
  
  return {
    reportTitle: 'LPG Consolidated Billing Report',
    periodStart: fromDate,
    periodEnd: toDate,
    devices: [], // No device breakdown in consolidated
    reportType: 'consolidated',
    summary: {
      totalDevices: gasData.device_count || 0,
      totalConsumption: gasData.total_consumption || 0,
      costPerLitre: 3,
      totalAmount: gasData.total_cost || 0,
      currency: gasData.currency || 'AED'
    }
  };
}
