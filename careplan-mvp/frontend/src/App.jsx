import { useState, useEffect, useRef } from 'react'

const styles = {
  container: {
    maxWidth: '900px',
    margin: '0 auto',
    padding: '20px',
  },
  header: {
    textAlign: 'center',
    marginBottom: '30px',
    color: '#333',
  },
  form: {
    background: 'white',
    padding: '30px',
    borderRadius: '8px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
    marginBottom: '20px',
  },
  section: {
    marginBottom: '25px',
    paddingBottom: '20px',
    borderBottom: '1px solid #eee',
  },
  sectionTitle: {
    fontSize: '18px',
    fontWeight: '600',
    marginBottom: '15px',
    color: '#444',
  },
  row: {
    display: 'flex',
    gap: '15px',
    marginBottom: '15px',
  },
  field: {
    flex: 1,
  },
  label: {
    display: 'block',
    marginBottom: '5px',
    fontWeight: '500',
    fontSize: '14px',
    color: '#555',
  },
  input: {
    width: '100%',
    padding: '10px 12px',
    border: '1px solid #ddd',
    borderRadius: '4px',
    fontSize: '14px',
    boxSizing: 'border-box',
  },
  textarea: {
    width: '100%',
    padding: '10px 12px',
    border: '1px solid #ddd',
    borderRadius: '4px',
    fontSize: '14px',
    minHeight: '80px',
    resize: 'vertical',
    boxSizing: 'border-box',
  },
  button: {
    background: '#0066cc',
    color: 'white',
    border: 'none',
    padding: '12px 30px',
    borderRadius: '4px',
    fontSize: '16px',
    cursor: 'pointer',
    width: '100%',
  },
  buttonDisabled: {
    background: '#999',
    cursor: 'not-allowed',
  },
  result: {
    background: 'white',
    padding: '30px',
    borderRadius: '8px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
  },
  status: {
    padding: '15px',
    borderRadius: '4px',
    marginBottom: '20px',
    textAlign: 'center',
  },
  statusPending: {
    background: '#fff3cd',
    color: '#856404',
  },
  statusProcessing: {
    background: '#cce5ff',
    color: '#004085',
  },
  statusCompleted: {
    background: '#d4edda',
    color: '#155724',
  },
  statusFailed: {
    background: '#f8d7da',
    color: '#721c24',
  },
  carePlan: {
    background: '#f8f9fa',
    padding: '20px',
    borderRadius: '4px',
    whiteSpace: 'pre-wrap',
    fontFamily: 'monospace',
    fontSize: '14px',
    lineHeight: '1.6',
    maxHeight: '500px',
    overflow: 'auto',
  },
  buttonRow: {
    display: 'flex',
    gap: '10px',
    marginTop: '15px',
  },
  downloadButton: {
    background: '#28a745',
    color: 'white',
    border: 'none',
    padding: '10px 20px',
    borderRadius: '4px',
    cursor: 'pointer',
    flex: 1,
  },
  checkStatusButton: {
    background: '#17a2b8',
    color: 'white',
    border: 'none',
    padding: '10px 20px',
    borderRadius: '4px',
    cursor: 'pointer',
    flex: 1,
  },
  orderInfo: {
    background: '#e9ecef',
    padding: '15px',
    borderRadius: '4px',
    marginBottom: '15px',
    fontSize: '14px',
  },
  orderId: {
    fontFamily: 'monospace',
    background: '#fff',
    padding: '4px 8px',
    borderRadius: '3px',
    fontSize: '13px',
  },
  // Search styles
  searchSection: {
    background: 'white',
    padding: '20px',
    borderRadius: '8px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
    marginBottom: '20px',
  },
  searchRow: {
    display: 'flex',
    gap: '10px',
  },
  searchInput: {
    flex: 1,
    padding: '10px 12px',
    border: '1px solid #ddd',
    borderRadius: '4px',
    fontSize: '14px',
  },
  searchButton: {
    background: '#6c757d',
    color: 'white',
    border: 'none',
    padding: '10px 20px',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '14px',
  },
  searchResults: {
    marginTop: '15px',
  },
  searchResultItem: {
    padding: '12px',
    borderBottom: '1px solid #eee',
    cursor: 'pointer',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  searchResultItemHover: {
    background: '#f8f9fa',
  },
  divider: {
    borderTop: '2px solid #dee2e6',
    margin: '30px 0',
  },
  inputError: {
    width: '100%',
    padding: '10px 12px',
    border: '1px solid #dc3545',
    borderRadius: '4px',
    fontSize: '14px',
    boxSizing: 'border-box',
  },
  errorText: {
    color: '#dc3545',
    fontSize: '12px',
    marginTop: '4px',
  },
}

// ── 前端校验规则（与后端 base.py 保持一致）──────────────────────────────
const ICD10_RE = /^[A-Za-z]\d{2}(\.\d{1,4})?$/

function validateForm(formData) {
  const errors = {}

  if (!/^\d{6}$/.test(formData.patient.mrn)) {
    errors['patient.mrn'] = 'MRN must be exactly 6 digits'
  }
  if (!/^\d{10}$/.test(formData.provider.npi)) {
    errors['provider.npi'] = 'NPI must be exactly 10 digits'
  }
  if (formData.medication.primary_diagnosis && !ICD10_RE.test(formData.medication.primary_diagnosis)) {
    errors['medication.primary_diagnosis'] = 'Invalid ICD-10 format (e.g. M06.9, G70.00)'
  }
  if (formData.medication.additional_diagnoses) {
    formData.medication.additional_diagnoses.split(',').map(s => s.trim()).filter(Boolean).forEach((code, i) => {
      if (!ICD10_RE.test(code)) {
        errors[`medication.additional_diagnoses[${i}]`] = `Invalid ICD-10 code: "${code}"`
      }
    })
  }

  return errors
}

function App() {
  const [formData, setFormData] = useState({
    patient: {
      first_name: '',
      last_name: '',
      dob: '',
      mrn: '',
    },
    provider: {
      name: '',
      npi: '',
    },
    medication: {
      name: '',
      primary_diagnosis: '',
      additional_diagnoses: '',
      medication_history: '',
    },
    patient_records: '',
  })

  const [fieldErrors, setFieldErrors] = useState({})
  const [pendingConfirm, setPendingConfirm] = useState(null) // { payload, warnings }

  const [loading, setLoading] = useState(false)
  const [checkingStatus, setCheckingStatus] = useState(false)
  const [result, setResult] = useState(null)

  // Polling state
  const [polling, setPolling] = useState(false)
  const pollingRef = useRef(null)

  // Auto-poll when result status is pending or processing
  useEffect(() => {
    if (polling && result?.order_id && (result.status === 'pending' || result.status === 'processing')) {
      pollingRef.current = setInterval(async () => {
        try {
          const response = await fetch(`/api/orders/${result.order_id}/`)
          const data = await response.json()
          setResult(data)
          if (data.status === 'completed' || data.status === 'failed') {
            setPolling(false)
          }
        } catch (error) {
          // Keep polling on network errors - don't stop
        }
      }, 3000)
    }

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
        pollingRef.current = null
      }
    }
  }, [polling, result?.order_id, result?.status])

  // Search state
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [searching, setSearching] = useState(false)

  const handleChange = (section, field, value) => {
    setFormData(prev => ({
      ...prev,
      [section]: typeof prev[section] === 'object'
        ? { ...prev[section], [field]: value }
        : value
    }))
  }

  // POST /api/orders/search/ - Search orders
  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      alert('Please enter search term')
      return
    }

    setSearching(true)
    try {
      const response = await fetch('/api/orders/search/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery }),
      })
      const data = await response.json()
      setSearchResults(data)
    } catch (error) {
      alert('Search failed: ' + error.message)
    } finally {
      setSearching(false)
    }
  }

  // Click search result to load order details
  const handleSelectOrder = async (orderId) => {
    setCheckingStatus(true)
    try {
      const response = await fetch(`/api/orders/${orderId}/`)
      const data = await response.json()
      setResult(data)
    } catch (error) {
      setResult({ status: 'failed', error: { message: error.message } })
    } finally {
      setCheckingStatus(false)
    }
  }

  // POST /api/orders/ - Submit form and get order_id
  const handleSubmit = async (e) => {
    e.preventDefault()
    setResult(null)

    // ── 前端校验 ─────────────────────────────────────────────────────────
    const errors = validateForm(formData)
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      return
    }
    setFieldErrors({})
    setLoading(true)

    const payload = {
      patient: formData.patient,
      provider: formData.provider,
      medication: {
        name: formData.medication.name,
        primary_diagnosis: formData.medication.primary_diagnosis,
        additional_diagnoses: formData.medication.additional_diagnoses
          ? formData.medication.additional_diagnoses.split(',').map(s => s.trim()).filter(Boolean)
          : [],
        medication_history: formData.medication.medication_history
          ? formData.medication.medication_history.split(',').map(s => s.trim()).filter(Boolean)
          : [],
      },
      patient_records: formData.patient_records,
    }

    try {
      const response = await fetch('/api/orders/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await response.json()

      if (!response.ok) {
        // ── WarningError：需要用户确认后重新提交 ─────────────────────────
        if (data.type === 'warning' && data.detail?.warnings) {
          setPendingConfirm({ payload, warnings: data.detail.warnings })
          setResult(null)
          return
        }
        // ── 其他 4xx：显示具体 field 错误 ────────────────────────────────
        if (data.detail?.errors) {
          const backendErrors = {}
          data.detail.errors.forEach(err => {
            backendErrors[err.field] = err.message
          })
          setFieldErrors(backendErrors)
        }
        setResult({ status: 'failed', error: { message: data.message || 'Request failed' } })
        return
      }

      setResult(data)
      if (data.order_id && data.status !== 'failed') {
        setPolling(true)
      }
    } catch (error) {
      setResult({
        status: 'failed',
        error: { message: error.message }
      })
    } finally {
      setLoading(false)
    }
  }

  // POST /api/orders/ with confirm=true - Resubmit after warning
  const handleConfirm = async () => {
    if (!pendingConfirm) return
    setLoading(true)
    setPendingConfirm(null)

    const payload = { ...pendingConfirm.payload, confirm: true }

    try {
      const response = await fetch('/api/orders/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await response.json()
      setResult(data)
      if (data.order_id && data.status !== 'failed') {
        setPolling(true)
      }
    } catch (error) {
      setResult({ status: 'failed', error: { message: error.message } })
    } finally {
      setLoading(false)
    }
  }

  // GET /api/orders/{order_id}/ - Check status
  const handleCheckStatus = async () => {
    if (!result || !result.order_id) return

    setCheckingStatus(true)

    try {
      const response = await fetch(`/api/orders/${result.order_id}/`)
      const data = await response.json()
      setResult(data)
    } catch (error) {
      setResult(prev => ({
        ...prev,
        error: { message: error.message }
      }))
    } finally {
      setCheckingStatus(false)
    }
  }

  const handleDownload = () => {
    if (result && result.order_id) {
      window.open(`/api/orders/${result.order_id}/download`, '_blank')
    }
  }

  const getStatusStyle = (status) => {
    switch (status) {
      case 'pending': return { ...styles.status, ...styles.statusPending }
      case 'processing': return { ...styles.status, ...styles.statusProcessing }
      case 'completed': return { ...styles.status, ...styles.statusCompleted }
      case 'failed': return { ...styles.status, ...styles.statusFailed }
      default: return styles.status
    }
  }

  const getStatusText = (status) => {
    switch (status) {
      case 'pending': return 'PENDING - Queued for processing'
      case 'processing': return 'PROCESSING - Generating Care Plan...'
      case 'completed': return 'COMPLETED'
      case 'failed': return 'FAILED'
      default: return status?.toUpperCase() || 'UNKNOWN'
    }
  }

  const getStatusBadge = (status) => {
    const colors = {
      pending: { bg: '#fff3cd', color: '#856404' },
      processing: { bg: '#cce5ff', color: '#004085' },
      completed: { bg: '#d4edda', color: '#155724' },
      failed: { bg: '#f8d7da', color: '#721c24' },
    }
    const style = colors[status] || { bg: '#eee', color: '#666' }
    return (
      <span style={{
        background: style.bg,
        color: style.color,
        padding: '2px 8px',
        borderRadius: '3px',
        fontSize: '12px',
      }}>
        {status}
      </span>
    )
  }

  return (
    <div style={styles.container}>
      <h1 style={styles.header}>Care Plan Generator</h1>

      {/* Search Section */}
      <div style={styles.searchSection}>
        <h2 style={styles.sectionTitle}>Search Orders</h2>
        <div style={styles.searchRow}>
          <input
            style={styles.searchInput}
            type="text"
            placeholder="Search by Order ID, Patient Name, MRN, or Medication..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
          <button
            style={searching ? { ...styles.searchButton, ...styles.buttonDisabled } : styles.searchButton}
            onClick={handleSearch}
            disabled={searching}
          >
            {searching ? 'Searching...' : 'Search'}
          </button>
        </div>

        {/* Search Results */}
        {searchResults && (
          <div style={styles.searchResults}>
            <p style={{ marginBottom: '10px', color: '#666' }}>
              Found {searchResults.count} order(s)
            </p>
            {searchResults.orders.map((order) => (
              <div
                key={order.order_id}
                style={styles.searchResultItem}
                onClick={() => handleSelectOrder(order.order_id)}
                onMouseEnter={(e) => e.currentTarget.style.background = '#f8f9fa'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'white'}
              >
                <div>
                  <span style={{ fontFamily: 'monospace', marginRight: '15px' }}>
                    {order.order_id.substring(0, 8)}...
                  </span>
                  <strong>{order.patient_name}</strong>
                  <span style={{ color: '#666', marginLeft: '10px' }}>
                    MRN: {order.patient_mrn}
                  </span>
                  <span style={{ color: '#666', marginLeft: '10px' }}>
                    {order.medication}
                  </span>
                </div>
                <div>
                  {getStatusBadge(order.status)}
                  <span style={{ color: '#999', marginLeft: '10px', fontSize: '12px' }}>
                    {new Date(order.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Divider */}
      <div style={styles.divider}></div>

      <form style={styles.form} onSubmit={handleSubmit}>
        {/* Patient Section */}
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Patient Information</h2>
          <div style={styles.row}>
            <div style={styles.field}>
              <label style={styles.label}>First Name *</label>
              <input
                style={styles.input}
                type="text"
                value={formData.patient.first_name}
                onChange={(e) => handleChange('patient', 'first_name', e.target.value)}
                required
              />
            </div>
            <div style={styles.field}>
              <label style={styles.label}>Last Name *</label>
              <input
                style={styles.input}
                type="text"
                value={formData.patient.last_name}
                onChange={(e) => handleChange('patient', 'last_name', e.target.value)}
                required
              />
            </div>
          </div>
          <div style={styles.row}>
            <div style={styles.field}>
              <label style={styles.label}>Date of Birth *</label>
              <input
                style={styles.input}
                type="date"
                value={formData.patient.dob}
                onChange={(e) => handleChange('patient', 'dob', e.target.value)}
                required
              />
            </div>
            <div style={styles.field}>
              <label style={styles.label}>MRN (6 digits) *</label>
              <input
                style={fieldErrors['patient.mrn'] ? styles.inputError : styles.input}
                type="text"
                maxLength={6}
                placeholder="e.g., 123456"
                value={formData.patient.mrn}
                onChange={(e) => {
                  handleChange('patient', 'mrn', e.target.value.replace(/\D/g, ''))
                  setFieldErrors(prev => ({ ...prev, 'patient.mrn': undefined }))
                }}
                required
              />
              {fieldErrors['patient.mrn'] && (
                <div style={styles.errorText}>⚠ {fieldErrors['patient.mrn']}</div>
              )}
            </div>
          </div>
        </div>

        {/* Provider Section */}
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Referring Provider</h2>
          <div style={styles.row}>
            <div style={styles.field}>
              <label style={styles.label}>Provider Name *</label>
              <input
                style={styles.input}
                type="text"
                value={formData.provider.name}
                onChange={(e) => handleChange('provider', 'name', e.target.value)}
                required
              />
            </div>
            <div style={styles.field}>
              <label style={styles.label}>NPI (10 digits) *</label>
              <input
                style={fieldErrors['provider.npi'] ? styles.inputError : styles.input}
                type="text"
                maxLength={10}
                placeholder="e.g., 1234567890"
                value={formData.provider.npi}
                onChange={(e) => {
                  handleChange('provider', 'npi', e.target.value.replace(/\D/g, ''))
                  setFieldErrors(prev => ({ ...prev, 'provider.npi': undefined }))
                }}
                required
              />
              {fieldErrors['provider.npi'] && (
                <div style={styles.errorText}>⚠ {fieldErrors['provider.npi']}</div>
              )}
            </div>
          </div>
        </div>

        {/* Medication Section */}
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Medication & Diagnosis</h2>
          <div style={styles.row}>
            <div style={styles.field}>
              <label style={styles.label}>Medication Name *</label>
              <input
                style={styles.input}
                type="text"
                value={formData.medication.name}
                onChange={(e) => handleChange('medication', 'name', e.target.value)}
                required
              />
            </div>
            <div style={styles.field}>
              <label style={styles.label}>Primary Diagnosis (ICD-10) *</label>
              <input
                style={fieldErrors['medication.primary_diagnosis'] ? styles.inputError : styles.input}
                type="text"
                placeholder="e.g., M06.9"
                value={formData.medication.primary_diagnosis}
                onChange={(e) => {
                  handleChange('medication', 'primary_diagnosis', e.target.value)
                  setFieldErrors(prev => ({ ...prev, 'medication.primary_diagnosis': undefined }))
                }}
                required
              />
              {fieldErrors['medication.primary_diagnosis'] && (
                <div style={styles.errorText}>⚠ {fieldErrors['medication.primary_diagnosis']}</div>
              )}
            </div>
          </div>
          <div style={styles.row}>
            <div style={styles.field}>
              <label style={styles.label}>Additional Diagnoses (comma separated)</label>
              <input
                style={styles.input}
                type="text"
                placeholder="e.g., I10, K21.9"
                value={formData.medication.additional_diagnoses}
                onChange={(e) => handleChange('medication', 'additional_diagnoses', e.target.value)}
              />
            </div>
          </div>
          <div style={styles.row}>
            <div style={styles.field}>
              <label style={styles.label}>Medication History (comma separated)</label>
              <input
                style={styles.input}
                type="text"
                placeholder="e.g., Pyridostigmine 60mg, Prednisone 10mg"
                value={formData.medication.medication_history}
                onChange={(e) => handleChange('medication', 'medication_history', e.target.value)}
              />
            </div>
          </div>
        </div>

        {/* Patient Records */}
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Patient Records (Optional)</h2>
          <textarea
            style={styles.textarea}
            placeholder="Paste relevant patient records or notes here..."
            value={formData.patient_records}
            onChange={(e) => setFormData(prev => ({ ...prev, patient_records: e.target.value }))}
          />
        </div>

        <button
          type="submit"
          style={loading ? { ...styles.button, ...styles.buttonDisabled } : styles.button}
          disabled={loading}
        >
          {loading ? 'Submitting...' : 'Generate Care Plan'}
        </button>
      </form>

      {/* ── Warning / Confirm Section ─────────────────────────────────── */}
      {pendingConfirm && (
        <div style={{
          background: '#fff8e1',
          border: '1px solid #f9a825',
          borderRadius: '8px',
          padding: '24px',
          marginBottom: '20px',
        }}>
          <h3 style={{ color: '#e65100', marginBottom: '12px' }}>
            ⚠ 检测到重复，请确认
          </h3>
          {pendingConfirm.warnings.map((w, i) => (
            <div key={i} style={{
              background: '#fff3e0',
              border: '1px solid #ffb74d',
              borderRadius: '4px',
              padding: '10px 14px',
              marginBottom: '8px',
              fontSize: '14px',
              color: '#e65100',
            }}>
              {w.message}
            </div>
          ))}
          <div style={{ display: 'flex', gap: '10px', marginTop: '16px' }}>
            <button
              style={{
                flex: 1,
                background: '#e65100',
                color: 'white',
                border: 'none',
                padding: '12px',
                borderRadius: '4px',
                fontSize: '15px',
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.7 : 1,
              }}
              onClick={handleConfirm}
              disabled={loading}
            >
              {loading ? '提交中...' : '确认，继续提交'}
            </button>
            <button
              style={{
                flex: 1,
                background: '#6c757d',
                color: 'white',
                border: 'none',
                padding: '12px',
                borderRadius: '4px',
                fontSize: '15px',
                cursor: 'pointer',
              }}
              onClick={() => setPendingConfirm(null)}
            >
              取消
            </button>
          </div>
        </div>
      )}

      {/* Result Section */}
      {result && (
        <div style={styles.result}>
          {/* Order Info */}
          {result.order_id && (
            <div style={styles.orderInfo}>
              <strong>Order ID:</strong> <span style={styles.orderId}>{result.order_id}</span>
              {result.patient && (
                <span style={{ marginLeft: '20px' }}>
                  <strong>Patient:</strong> {result.patient.name} (MRN: {result.patient.mrn})
                </span>
              )}
              {result.medication && (
                <span style={{ marginLeft: '20px' }}>
                  <strong>Medication:</strong> {result.medication}
                </span>
              )}
            </div>
          )}

          {/* Status Badge */}
          <div style={getStatusStyle(result.status)}>
            <strong>Status: {getStatusText(result.status)}</strong>
            {result.message && <p style={{ margin: '5px 0 0 0' }}>{result.message}</p>}
          </div>

          {/* Polling indicator or manual Check Status - Show when pending or processing */}
          {(result.status === 'pending' || result.status === 'processing') && (
            polling ? (
              <div style={{ textAlign: 'center', padding: '10px', color: '#004085' }}>
                Auto-checking every 3 seconds...
                <button
                  style={{ ...styles.checkStatusButton, marginTop: '10px', background: '#6c757d' }}
                  onClick={() => setPolling(false)}
                >
                  Stop Auto-Check
                </button>
              </div>
            ) : (
              <button
                style={checkingStatus ? { ...styles.checkStatusButton, ...styles.buttonDisabled } : styles.checkStatusButton}
                onClick={() => { handleCheckStatus(); setPolling(true); }}
                disabled={checkingStatus}
              >
                {checkingStatus ? 'Checking...' : 'Check Status'}
              </button>
            )
          )}

          {/* Care Plan Content - Show when completed */}
          {result.status === 'completed' && result.care_plan && (
            <>
              <h3 style={{ marginBottom: '15px' }}>Generated Care Plan</h3>
              <div style={styles.carePlan}>
                {result.care_plan.content}
              </div>
              <div style={styles.buttonRow}>
                <button style={styles.downloadButton} onClick={handleDownload}>
                  Download Care Plan (.txt)
                </button>
                <button style={styles.checkStatusButton} onClick={handleCheckStatus}>
                  Refresh
                </button>
              </div>
            </>
          )}

          {/* Error Message - Show when failed */}
          {result.status === 'failed' && result.error && (
            <div style={{ color: '#721c24' }}>
              <strong>Error:</strong> {result.error.message}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default App
