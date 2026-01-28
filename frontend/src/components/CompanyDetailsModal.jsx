import { useState, useEffect } from "react";
import Icon from "./Icon";
import { getCompanyDetails, saveCompanyDetails } from "../utils/pdfReportGenerator";

/**
 * Modal for editing company details used in billing reports
 */
export default function CompanyDetailsModal({ isOpen, onClose }) {
  const [details, setDetails] = useState(getCompanyDetails());
  const [logoPreview, setLogoPreview] = useState(null);
  const [saving, setSaving] = useState(false);
  const [templatePreview, setTemplatePreview] = useState(null);
  
  useEffect(() => {
    if (isOpen) {
      const current = getCompanyDetails();
      setDetails(current);
      setLogoPreview(current.logo);
      setTemplatePreview(current.customTemplate);
    }
  }, [isOpen]);
  
  const handleLogoUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert('Please upload an image file');
      return;
    }
    
    // Validate file size (max 500KB)
    if (file.size > 500 * 1024) {
      alert('Logo file must be less than 500KB');
      return;
    }
    
    const reader = new FileReader();
    reader.onload = (event) => {
      const base64 = event.target.result;
      setLogoPreview(base64);
      setDetails(prev => ({ ...prev, logo: base64 }));
    };
    reader.readAsDataURL(file);
  };
  
  const handleRemoveLogo = () => {
    setLogoPreview(null);
    setDetails(prev => ({ ...prev, logo: null }));
  };
  
  const handleTemplateUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    // Validate file type
    if (!file.name.endsWith('.html')) {
      alert('Please upload an HTML file (.html)');
      return;
    }
    
    // Validate file size (max 500KB)
    if (file.size > 500 * 1024) {
      alert('Template file must be less than 500KB');
      return;
    }
    
    const reader = new FileReader();
    reader.onload = (event) => {
      const templateContent = event.target.result;
      setTemplatePreview(templateContent);
      setDetails(prev => ({ ...prev, customTemplate: templateContent }));
    };
    reader.readAsText(file);
  };
  
  const handleRemoveTemplate = () => {
    setTemplatePreview(null);
    setDetails(prev => ({ ...prev, customTemplate: null }));
  };
  
  const handleSave = () => {
    // Validate required fields
    if (!details.headerText || !details.headerText.trim()) {
      alert('Header Text is required. Please enter header text for reports.');
      return;
    }
    if (!details.footerText || !details.footerText.trim()) {
      alert('Footer Text is required. Please enter footer text for reports.');
      return;
    }
    
    setSaving(true);
    saveCompanyDetails(details);
    setTimeout(() => {
      setSaving(false);
      onClose();
    }, 500);
  };
  
  if (!isOpen) return null;
  
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '600px' }}>
        <div className="modal-header">
          <h2 className="modal-title">
            <Icon name="edit" size={24} />
            Company Details for Reports
          </h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            <Icon name="x" size={20} />
          </button>
        </div>
        
        <div className="modal-body">
          <div className="form">
            {/* Logo Upload */}
            <div className="form-group">
              <label className="form-label">
                <Icon name="image" size={16} />
                Company Logo
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
                {logoPreview && (
                  <div style={{ 
                    border: '2px solid var(--color-border)', 
                    borderRadius: 'var(--radius-md)',
                    padding: 'var(--space-3)',
                    background: 'var(--color-bg-secondary)'
                  }}>
                    <img 
                      src={logoPreview} 
                      alt="Logo Preview" 
                      style={{ 
                        maxWidth: '150px', 
                        maxHeight: '80px',
                        display: 'block'
                      }} 
                    />
                  </div>
                )}
                <div style={{ flex: 1 }}>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleLogoUpload}
                    style={{ marginBottom: 'var(--space-2)' }}
                    className="form-input"
                  />
                  {logoPreview && (
                    <button 
                      type="button"
                      className="btn btn--sm btn--error"
                      onClick={handleRemoveLogo}
                    >
                      <Icon name="trash" size={14} />
                      Remove Logo
                    </button>
                  )}
                  <p className="text-muted" style={{ fontSize: 'var(--font-size-xs)', marginTop: 'var(--space-2)' }}>
                    Max size: 500KB. Recommended: 300x150px
                  </p>
                </div>
              </div>
            </div>
            
            {/* Company Name */}
            <div className="form-group">
              <label className="form-label" htmlFor="companyName">
                <Icon name="building" size={16} />
                Company Name
              </label>
              <input
                id="companyName"
                type="text"
                className="form-input"
                value={details.companyName}
                onChange={(e) => setDetails(prev => ({ ...prev, companyName: e.target.value }))}
                placeholder="Enter company name"
              />
            </div>
            
            {/* Address */}
            <div className="form-group">
              <label className="form-label" htmlFor="address">
                <Icon name="map-pin" size={16} />
                Address
              </label>
              <textarea
                id="address"
                className="form-input"
                rows="2"
                value={details.address}
                onChange={(e) => setDetails(prev => ({ ...prev, address: e.target.value }))}
                placeholder="Enter company address"
              />
            </div>
            
            {/* Phone and Email */}
            <div className="form-grid">
              <div className="form-group">
                <label className="form-label" htmlFor="phone">
                  <Icon name="phone" size={16} />
                  Phone
                </label>
                <input
                  id="phone"
                  type="text"
                  className="form-input"
                  value={details.phone}
                  onChange={(e) => setDetails(prev => ({ ...prev, phone: e.target.value }))}
                  placeholder="+971 4 XXX XXXX"
                />
              </div>
              
              <div className="form-group">
                <label className="form-label" htmlFor="email">
                  <Icon name="mail" size={16} />
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  className="form-input"
                  value={details.email}
                  onChange={(e) => setDetails(prev => ({ ...prev, email: e.target.value }))}
                  placeholder="billing@company.com"
                />
              </div>
            </div>
            
            {/* Tax ID */}
            <div className="form-group">
              <label className="form-label" htmlFor="taxId">
                <Icon name="file" size={16} />
                Tax Registration Number (TRN)
              </label>
              <input
                id="taxId"
                type="text"
                className="form-input"
                value={details.taxId}
                onChange={(e) => setDetails(prev => ({ ...prev, taxId: e.target.value }))}
                placeholder="TRN: 100000000000003"
              />
            </div>
            
            {/* Header Text */}
            <div className="form-group">
              <label className="form-label" htmlFor="headerText">
                <Icon name="type" size={16} />
                Header Text <span style={{ color: 'var(--color-error)' }}>*</span>
              </label>
              <textarea
                id="headerText"
                className="form-input"
                rows="3"
                value={details.headerText || ''}
                onChange={(e) => setDetails(prev => ({ ...prev, headerText: e.target.value }))}
                placeholder="Enter header text to display at the top of reports"
                required
              />
              <p className="text-muted" style={{ fontSize: 'var(--font-size-xs)', marginTop: 'var(--space-2)' }}>
                This text will appear at the top of the report (required)
              </p>
            </div>
            
            {/* Footer Text */}
            <div className="form-group">
              <label className="form-label" htmlFor="footerText">
                <Icon name="type" size={16} />
                Footer Text <span style={{ color: 'var(--color-error)' }}>*</span>
              </label>
              <textarea
                id="footerText"
                className="form-input"
                rows="3"
                value={details.footerText || ''}
                onChange={(e) => setDetails(prev => ({ ...prev, footerText: e.target.value }))}
                placeholder="Enter footer text to display at the bottom of reports"
                required
              />
              <p className="text-muted" style={{ fontSize: 'var(--font-size-xs)', marginTop: 'var(--space-2)' }}>
                This text will appear at the bottom of the report (required)
              </p>
            </div>
            
            {/* Custom Template Upload */}
            <div className="form-group">
              <label className="form-label">
                <Icon name="file" size={16} />
                Custom Report Template (Optional)
              </label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                <input
                  type="file"
                  accept=".html"
                  onChange={handleTemplateUpload}
                  className="form-input"
                />
                {templatePreview && (
                  <>
                    <div style={{ 
                      padding: 'var(--space-3)', 
                      background: 'var(--color-bg-secondary)', 
                      border: '1px solid var(--color-border)',
                      borderRadius: 'var(--radius-md)',
                      maxHeight: '200px',
                      overflow: 'auto',
                      fontSize: 'var(--font-size-xs)',
                      fontFamily: 'monospace'
                    }}>
                      <div style={{ fontWeight: 'bold', marginBottom: 'var(--space-2)' }}>
                        Template Preview (first 500 chars):
                      </div>
                      <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                        {templatePreview.substring(0, 500)}{templatePreview.length > 500 ? '...' : ''}
                      </pre>
                    </div>
                    <button 
                      type="button"
                      className="btn btn--sm btn--error"
                      onClick={handleRemoveTemplate}
                    >
                      <Icon name="trash" size={14} />
                      Remove Custom Template
                    </button>
                  </>
                )}
                <div>
                  <p className="text-muted" style={{ fontSize: 'var(--font-size-xs)', marginTop: 'var(--space-2)' }}>
                    Upload a custom HTML template to override the default report layout. Max size: 500KB.
                    <a 
                      href="/report-template-example.html" 
                      download 
                      style={{ marginLeft: 'var(--space-2)', color: 'var(--color-primary)' }}
                    >
                      Download example template
                    </a>
                  </p>
                  <details style={{ marginTop: 'var(--space-2)' }}>
                    <summary style={{ cursor: 'pointer', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)' }}>
                      Available template variables
                    </summary>
                    <div style={{ 
                      marginTop: 'var(--space-2)', 
                      padding: 'var(--space-3)', 
                      background: 'var(--color-bg-secondary)',
                      borderRadius: 'var(--radius-md)',
                      fontSize: 'var(--font-size-xs)',
                      fontFamily: 'monospace'
                    }}>
                      <div><strong>Company:</strong> {'{{companyName}}'}, {'{{companyAddress}}'}, {'{{companyPhone}}'}, {'{{companyEmail}}'}, {'{{companyTaxId}}'}, {'{{companyLogo}}'}</div>
                      <div style={{ marginTop: 'var(--space-2)' }}><strong>Report:</strong> {'{{reportTitle}}'}, {'{{periodStart}}'}, {'{{periodEnd}}'}, {'{{generatedDate}}'}</div>
                      <div style={{ marginTop: 'var(--space-2)' }}><strong>Summary:</strong> {'{{totalDevices}}'}, {'{{totalConsumption}}'}, {'{{costPerLitre}}'}, {'{{totalAmount}}'}, {'{{currency}}'}</div>
                      <div style={{ marginTop: 'var(--space-2)' }}><strong>Content:</strong> {'{{headerText}}'}, {'{{footerText}}'}, {'{{deviceTable}}'}</div>
                    </div>
                  </details>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div className="modal-footer">
          <button className="btn btn--secondary" onClick={onClose} disabled={saving}>
            <Icon name="x" size={16} />
            Cancel
          </button>
          <button className="btn btn--primary" onClick={handleSave} disabled={saving}>
            <Icon name={saving ? "activity" : "check"} size={16} />
            {saving ? 'Saving...' : 'Save Details'}
          </button>
        </div>
      </div>
    </div>
  );
}
