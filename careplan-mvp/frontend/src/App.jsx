import { useState } from 'react'

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

  const [loading, setLoading] = useState(false)
  const [checkingStatus, setCheckingStatus] = useState(false)
  const [result, setResult] = useState(null)

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
    setLoading(true)
    setResult(null)

    const payload = {
      patient: formData.patient,
      provider: formData.provider,
      medication: {
        name: formData.medication.name,
        primary_diagnosis: formData.medication.primary_diagnosis,
        additional_diagnoses: formData.medication.additional_diagnoses
          ? formData.medication.additional_diagnoses.split(',').map(s => s.trim())
          : [],
        medication_history: formData.medication.medication_history
          ? formData.medication.medication_history.split(',').map(s => s.trim())
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
      setResult(data)
    } catch (error) {
      setResult({
        status: 'failed',
        error: { message: error.message }
      })
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
                style={styles.input}
                type="text"
                maxLength={6}
                value={formData.patient.mrn}
                onChange={(e) => handleChange('patient', 'mrn', e.target.value)}
                required
              />
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
                style={styles.input}
                type="text"
                maxLength={10}
                value={formData.provider.npi}
                onChange={(e) => handleChange('provider', 'npi', e.target.value)}
                required
              />
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
                style={styles.input}
                type="text"
                placeholder="e.g., G70.00"
                value={formData.medication.primary_diagnosis}
                onChange={(e) => handleChange('medication', 'primary_diagnosis', e.target.value)}
                required
              />
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

          {/* Check Status Button - Show when pending or processing */}
          {(result.status === 'pending' || result.status === 'processing') && (
            <button
              style={checkingStatus ? { ...styles.checkStatusButton, ...styles.buttonDisabled } : styles.checkStatusButton}
              onClick={handleCheckStatus}
              disabled={checkingStatus}
            >
              {checkingStatus ? 'Checking...' : 'Check Status'}
            </button>
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
