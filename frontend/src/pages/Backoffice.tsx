import React, { useState, useEffect, ChangeEvent, FormEvent, useRef } from 'react';
import axios from 'axios';
import { Endpoints, GRAFANA_BASE } from '../api/endpoints';
import { useNavigate } from 'react-router-dom';
import { sessionHeaders, csrfHeaders } from '../utils/authUtils';
import './Backoffice.css';

interface Product {
    product_id: string;
    category: string;
    question_en: string;
    answer_en: string;
    question_ar: string;
    answer_ar: string;
}

/*
interface GuardrailsConfig {
    is_safe_input: boolean;
    enforce_anonymous_mode: boolean;
    block_financial_advisory: boolean;
    escalation_trigger: boolean;
    restrict_to_topic: boolean;
    detect_pii_input: boolean;
    secrets_present_input: boolean;
    toxic_language: boolean;
    detect_pii_output: boolean;
    secrets_present_output: boolean;
    is_safe_output: boolean;
    valid_topics: string[];
    invalid_topics: string[];
}
*/

interface BackofficeProps {
    sessionId: string;
}

/*
const validatorDescriptions: Record<string, string> = {
    is_safe_input: "Analyzes user input for common LLM injection patterns, prompt leakage attempts, and dangerous command keywords like 'DROP TABLE' or 'BYPASS'.",
    enforce_anonymous_mode: "Ensures privacy by blocking requests that contain phrases related to personal bank accounts, balances, or specific transactions, keeping the session anonymous.",
    block_financial_advisory: "Prevents the model from giving specific investment advice or recommending financial products beyond general information, mitigating legal risks.",
    escalation_trigger: "Monitors for high-sensitivity keywords like 'fraud', 'stolen', or 'lawsuit', and automatically flags the conversation for immediate human intervention.",
    restrict_to_topic: "Uses semantic analysis to ensure the user's query is relevant to the allowed banking topics. Messages outside these topics will be blocked.",
    detect_pii_input: "Scans for and blocks sensitive Personal Identifiable Information (PII) like emails, phone numbers, and SSNs from being processed by the LLM.",
    secrets_present_input: "Detects the presence of sensitive credentials, API keys, or passwords in the user's message to prevent accidental exposure.",
    toxic_language: "Uses an advanced multilingual LLM to filter out offensive, hateful, or inappropriate language to maintain a professional environment.",
    detect_pii_output: "Ensures the AI agent does not inadvertently leak sensitive data in its response, providing a final layer of protection for customer privacy.",
    secrets_present_output: "Verifies that the AI's generated response doesn't contain any internal system keys, tokens, or back-end secrets.",
    is_safe_output: "A final catch-all safety check to ensure the response is helpful, professional, and doesn't contain any restricted content."
};
*/

export default function Backoffice({ sessionId }: BackofficeProps) {
    const [products, setProducts] = useState<Product[]>([]);
    const [file, setFile] = useState<File | null>(null);
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState('');
    const [showModal, setShowModal] = useState(false);
    const [currentProduct, setCurrentProduct] = useState<Partial<Product>>({
        category: 'General',
        question_en: '',
        answer_en: '',
        question_ar: '',
        answer_ar: ''
    });

    /*
    const [config, setConfig] = useState<GuardrailsConfig | null>(null);
    const [savingConfig, setSavingConfig] = useState(false);
    const [newTopic, setNewTopic] = useState('');
    const [newInvalidTopic, setNewInvalidTopic] = useState('');
    const [activeTooltip, setActiveTooltip] = useState<string | null>(null);
    */

    const navigate = useNavigate();
    const fileInputRef = useRef<HTMLInputElement>(null);

    const axiosConfig = {
        headers: {
            ...sessionHeaders(sessionId),
            ...csrfHeaders(sessionId)
        },
        withCredentials: true
    };

    useEffect(() => {
        fetchProducts();
        // fetchConfig();
    }, []);

    /*
    const fetchConfig = async () => {
        try {
            const res = await axios.get(Endpoints.GUARDRAILS_CONFIG, axiosConfig);
            if (res.data) {
                setConfig(res.data);
            }
        } catch (err) {
            console.error("Failed to fetch configuration", err);
        }
    };
    */

    const fetchProducts = async () => {
        try {
            const res = await axios.get(Endpoints.BACKOFFICE_PRODUCTS, axiosConfig);
            if (res.data.success) {
                setProducts(res.data.products || res.data);
            }
        } catch (err) {
            console.error("Failed to fetch products", err);
            setMessage("Error: Failed to load products from database.");
        }
    };

    const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            setFile(e.target.files[0]);
        }
    };

    const handleUpload = async () => {
        if (!file) return;
        setLoading(true);
        setMessage('');
        const formData = new FormData();
        formData.append("file", file);
        try {
            const res = await axios.post(Endpoints.BACKOFFICE_UPLOAD, formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                    ...sessionHeaders(sessionId),
                    ...csrfHeaders(sessionId)
                },
                withCredentials: true
            });
            if (res.data.success) {
                setMessage('Success: ' + res.data.message);
                setFile(null);
                if (fileInputRef.current) {
                    fileInputRef.current.value = '';
                }
                fetchProducts();
            } else {
                setMessage('Error: ' + (res.data.message || res.data.error || 'Upload failed'));
            }
        } catch (err: any) {
            setMessage('Error: Upload failed - ' + (err.response?.data?.detail || err.response?.data?.error || err.message));
        } finally {
            setLoading(false);
        }
    };

    const handleUpsert = async (e: FormEvent) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await axios.post(Endpoints.BACKOFFICE_UPSERT, currentProduct, axiosConfig);
            if (res.data.success) {
                setMessage('Success: Product saved successfully!');
                setShowModal(false);
                fetchProducts();
            } else {
                setMessage('Error: ' + (res.data.message || res.data.error || 'Save failed'));
            }
        } catch (err: any) {
            setMessage('Error: Save failed - ' + (err.response?.data?.detail || err.response?.data?.error || err.message));
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (productId: string) => {
        if (!window.confirm(`Are you sure you want to delete this product?\n\n Note: Any changes will take effect for users upon their next login. Currently active sessions will not be affected until the user logs out.`)) return;
        try {
            const res = await axios.delete(Endpoints.BACKOFFICE_DELETE(productId), axiosConfig);
            if (res.data.success) {
                setMessage(`Success: Deleted product`);
                fetchProducts();
            } else {
                setMessage('Error: ' + (res.data.error || 'Delete failed'));
            }
        } catch (err: any) {
            setMessage('Error: Delete failed - ' + (err.response?.data?.detail || err.response?.data?.error || err.message));
        }
    };

    const handleDeleteAll = async () => {
        if (!window.confirm(`ARE YOU SURE? This will permanently delete ALL products from the database.\n\n Note: Any changes will take effect for users upon their next login. Currently active sessions will not be affected until the user logs out.`)) return;
        setLoading(true);
        try {
            const res = await axios.delete(Endpoints.BACKOFFICE_CLEAR, axiosConfig);
            if (res.data.success) {
                setMessage("Success: Cleared the entire database.");
                fetchProducts();
            } else {
                setMessage('Error: ' + (res.data.error || 'Clear failed'));
            }
        } catch (err: any) {
            setMessage('Error: Clear failed - ' + (err.response?.data?.detail || err.response?.data?.error || err.message));
        } finally {
            setLoading(false);
        }
    };

    const openModal = (product?: Product) => {
        if (product) {
            setCurrentProduct(product);
        } else {
            setCurrentProduct({ category: 'General', question_en: '', answer_en: '', question_ar: '', answer_ar: '' });
        }
        setShowModal(true);
    };

    /*
    const handleConfigToggle = (key: keyof GuardrailsConfig) => {
        if (!config) return;
        setConfig({ ...config, [key]: !config[key as keyof GuardrailsConfig] });
    };

    const handleAddTopic = () => {
        if (!config || !newTopic.trim()) return;
        if (!config.valid_topics.includes(newTopic.trim())) {
            setConfig({
                ...config,
                valid_topics: [...config.valid_topics, newTopic.trim()]
            });
        }
        setNewTopic('');
    };

    const handleRemoveTopic = (topic: string) => {
        if (!config) return;
        setConfig({
            ...config,
            valid_topics: config.valid_topics.filter((t: string) => t !== topic)
        });
    };

    const handleAddInvalidTopic = () => {
        if (!config || !newInvalidTopic.trim()) return;
        if (!config.invalid_topics.includes(newInvalidTopic.trim())) {
            setConfig({
                ...config,
                invalid_topics: [...config.invalid_topics, newInvalidTopic.trim()]
            });
        }
        setNewInvalidTopic('');
    };

    const handleRemoveInvalidTopic = (topic: string) => {
        if (!config) return;
        setConfig({
            ...config,
            invalid_topics: config.invalid_topics.filter((t: string) => t !== topic)
        });
    };

    const handleSelectAllValidators = () => {
        if (!config) return;
        const newConfig = { ...config };
        Object.keys(validatorDescriptions).forEach(key => {
            (newConfig as any)[key] = true;
        });
        setConfig(newConfig);
    };

    const handleDeselectAllValidators = () => {
        if (!config) return;
        const newConfig = { ...config };
        Object.keys(validatorDescriptions).forEach(key => {
            (newConfig as any)[key] = false;
        });
        setConfig(newConfig);
    };

    const handleRemoveAllTopics = () => {
        if (!config) return;
        if (window.confirm("Are you sure you want to remove all valid topics?")) {
            setConfig({ ...config, valid_topics: [] });
        }
    };

    const handleRemoveAllInvalidTopics = () => {
        if (!config) return;
        if (window.confirm("Are you sure you want to remove all invalid topics?")) {
            setConfig({ ...config, invalid_topics: [] });
        }
    };

    const handleSaveConfig = async () => {
        if (!config) return;
        setSavingConfig(true);
        try {
            const res = await axios.post(Endpoints.GUARDRAILS_CONFIG, config, axiosConfig);
            if (res.data) {
                setConfig(res.data);
                setMessage("Success: Guardrails configuration updated!");
            }
        } catch (err: any) {
            setMessage('Error: Failed to save config - ' + (err.response?.data?.detail || err.response?.data?.error || err.message));
        } finally {
            setSavingConfig(false);
        }
    };
    */


    return (
        <div className="backoffice-container">
            <header className="backoffice-header">
                <h1>Document Backoffice</h1>
                <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                    <button onClick={() => window.open(`${GRAFANA_BASE}/d/poc_effectiveness/poc-effectiveness-dashboard`, '_blank')} className="btn btn-primary">Analysis Dashboard</button>
                    <button onClick={() => openModal()} className="btn btn-success">+ Add New</button>
                    <button onClick={() => navigate('/session-explorer')} className="btn btn-primary">Session Explorer</button>
                    <button onClick={() => navigate('/chat')} className="btn btn-secondary">Back to Chat</button>
                </div>
            </header>

            {message && (
                <div className={`alert ${message.toLowerCase().includes('error') ? 'alert-error' : 'alert-success'}`}>
                    {message}
                </div>
            )}

            <section className="section-card">
                <h3>Bulk Ingest (Excel)</h3>
                <div className="upload-controls">
                    <input type="file" accept=".xlsx,.xls" onChange={handleFileChange} ref={fileInputRef} />
                    <button onClick={handleUpload} disabled={!file || loading} className="btn btn-primary">
                        {loading ? 'Uploading...' : 'Ingest File'}
                    </button>
                </div>
            </section>

            {/* <section className="section-card">
                <h2>Guardrails Configuration</h2>
                <p style={{ marginBottom: '1.5rem', fontSize: '0.9rem', color: '#555' }}>Manage the AI agent's validation rules and allowed topics.</p>

                {config ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>

                        <section className="section-card" style={{ marginBottom: 0 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                                <h3 style={{ margin: 0 }}>Validator Enforcement</h3>
                                <div style={{ display: 'flex', gap: '0.5rem' }}>
                                    <button
                                        type="button"
                                        className="btn btn-secondary"
                                        style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                                        onClick={handleSelectAllValidators}
                                    >
                                        Enable All
                                    </button>
                                    <button
                                        type="button"
                                        className="btn btn-secondary"
                                        style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                                        onClick={handleDeselectAllValidators}
                                    >
                                        Disable All
                                    </button>
                                </div>
                            </div>
                            <p style={{ marginBottom: '1.5rem', fontSize: '0.85rem', color: '#666' }}>Enable or disable specific validation rules for the AI agent.</p>

                            <div style={{
                                display: 'grid',
                                gridTemplateColumns: 'repeat(3, 1fr)', // Fixed 3-column layout for stability
                                gap: '1.25rem'
                            }}>
                                {Object.entries(config)
                                    .filter(([key]) => key !== 'valid_topics' && key !== 'invalid_topics')
                                    .map(([key, value]) => (
                                        <div key={key} className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', margin: 0, position: 'relative' }}>
                                            <label className="switch" style={{ position: 'relative', display: 'inline-block', width: '36px', height: '18px', flexShrink: 0 }}>
                                                <input
                                                    type="checkbox"
                                                    checked={value as boolean}
                                                    onChange={() => handleConfigToggle(key as keyof GuardrailsConfig)}
                                                    style={{ opacity: 0, width: 0, height: 0 }}
                                                />
                                                <span className="slider round" style={{
                                                    position: 'absolute', cursor: 'pointer', top: 0, left: 0, right: 0, bottom: 0,
                                                    backgroundColor: value ? '#2ecc71' : '#ccc', transition: '.4s', borderRadius: '34px'
                                                }}>
                                                    <span style={{
                                                        position: 'absolute', content: '""', height: '14px', width: '14px',
                                                        left: value ? '19px' : '3px', bottom: '2px', backgroundColor: 'white',
                                                        transition: '.4s', borderRadius: '50%'
                                                    }} />
                                                </span>
                                            </label>
                                            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', cursor: 'pointer', minWidth: 0 }} onClick={() => setActiveTooltip(activeTooltip === key ? null : key)}>
                                                <span style={{
                                                    fontSize: '0.8rem',
                                                    textTransform: 'capitalize',
                                                    color: '#333',
                                                    fontWeight: 500,
                                                    whiteSpace: 'nowrap',
                                                    overflow: 'hidden',
                                                    textOverflow: 'ellipsis'
                                                }}>
                                                    {key.split('_').join(' ')}
                                                </span>
                                                <span
                                                    style={{
                                                        background: '#3498db', border: 'none', borderRadius: '50%',
                                                        width: '14px', height: '14px', fontSize: '10px', flexShrink: 0,
                                                        display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white',
                                                        boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
                                                    }}
                                                >
                                                    ?
                                                </span>
                                            </div>
                                            {activeTooltip === key && (
                                                <div
                                                    style={{
                                                        position: 'absolute', top: '100%', left: '0', zIndex: 100,
                                                        width: '280px',
                                                        background: '#2c3e50', color: '#ecf0f1', padding: '0.75rem', borderRadius: '8px',
                                                        fontSize: '0.75rem', marginTop: '6px', lineHeight: '1.4',
                                                        boxShadow: '0 4px 15px rgba(0,0,0,0.3)',
                                                        border: '1px solid #34495e'
                                                    }}
                                                    onClick={() => setActiveTooltip(null)}
                                                >
                                                    <div style={{ fontWeight: 'bold', marginBottom: '4px', textTransform: 'capitalize', color: '#3498db' }}>{key.split('_').join(' ')}</div>
                                                    {validatorDescriptions[key] || "No description available."}
                                                    <div style={{ marginTop: '6px', fontSize: '0.65rem', color: '#bdc3c7', textAlign: 'right', fontStyle: 'italic' }}>Click to close</div>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                            </div>
                        </section>

                        <section className="section-card" style={{ marginTop: 0 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                                <h3 style={{ margin: 0 }}>Valid Topics Management</h3>
                                {config.valid_topics.length > 0 && (
                                    <button
                                        type="button"
                                        className="btn btn-danger"
                                        style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                                        onClick={handleRemoveAllTopics}
                                    >
                                        Remove All Topics
                                    </button>
                                )}
                            </div>
                            <p style={{ fontSize: '0.85rem', color: '#666', marginBottom: '1rem' }}>These topics define the allowed scope for user inquiries.</p>

                            <div style={{
                                display: 'flex',
                                flexWrap: 'wrap',
                                gap: '0.5rem',
                                marginBottom: '1.5rem',
                                minHeight: '44px',
                                background: '#f9f9f9',
                                padding: '0.75rem',
                                borderRadius: '8px',
                                border: '1px solid #eee'
                            }}>
                                {config.valid_topics.length === 0 ? (
                                    <span style={{ color: '#999', fontSize: '0.8rem', fontStyle: 'italic' }}>No topics configured.</span>
                                ) : (
                                    config.valid_topics.map((topic: string) => (
                                        <span key={topic} style={{ background: '#e1f5fe', color: '#0277bd', padding: '0.3rem 0.75rem', borderRadius: '16px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.5rem', border: '1px solid #b3e5fc' }}>
                                            {topic}
                                            <button onClick={() => handleRemoveTopic(topic)} style={{ background: 'none', border: 'none', color: '#01579b', cursor: 'pointer', outline: 'none', padding: 0, fontSize: '1.1rem', lineHeight: 1, fontWeight: 'bold' }}>&times;</button>
                                        </span>
                                    ))
                                )}
                            </div>

                            <div style={{ display: 'flex', gap: '0.5rem', maxWidth: '450px' }}>
                                <input
                                    type="text"
                                    className="form-control"
                                    value={newTopic}
                                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewTopic(e.target.value)}
                                    placeholder="Enter new banking topic (e.g. Loans)"
                                    onKeyPress={(e: React.KeyboardEvent<HTMLInputElement>) => e.key === 'Enter' && handleAddTopic()}
                                />
                                <button onClick={handleAddTopic} className="btn btn-secondary" style={{ whiteSpace: 'nowrap' }}>Add Topic</button>
                            </div>
                        </section>

                        <section className="section-card" style={{ marginTop: 0 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                                <h3 style={{ margin: 0 }}>Invalid Topics / Escalation Triggers</h3>
                                {config.invalid_topics && config.invalid_topics.length > 0 && (
                                    <button
                                        type="button"
                                        className="btn btn-danger"
                                        style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                                        onClick={handleRemoveAllInvalidTopics}
                                    >
                                        Remove All Invalid Topics
                                    </button>
                                )}
                            </div>
                            <p style={{ fontSize: '0.85rem', color: '#666', marginBottom: '1rem' }}>These topics are strictly forbidden. Mentioning them will trigger an immediate escalation to a supervisor.</p>

                            <div style={{
                                display: 'flex',
                                flexWrap: 'wrap',
                                gap: '0.5rem',
                                marginBottom: '1.5rem',
                                minHeight: '44px',
                                background: '#fff0f0',
                                padding: '0.75rem',
                                borderRadius: '8px',
                                border: '1px solid #ffcdd2'
                            }}>
                                {!config.invalid_topics || config.invalid_topics.length === 0 ? (
                                    <span style={{ color: '#999', fontSize: '0.8rem', fontStyle: 'italic' }}>No invalid topics configured.</span>
                                ) : (
                                    config.invalid_topics.map((topic: string) => (
                                        <span key={topic} style={{ background: '#ffebee', color: '#c62828', padding: '0.3rem 0.75rem', borderRadius: '16px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.5rem', border: '1px solid #ffcdd2' }}>
                                            {topic}
                                            <button onClick={() => handleRemoveInvalidTopic(topic)} style={{ background: 'none', border: 'none', color: '#b71c1c', cursor: 'pointer', outline: 'none', padding: 0, fontSize: '1.1rem', lineHeight: 1, fontWeight: 'bold' }}>&times;</button>
                                        </span>
                                    ))
                                )}
                            </div>

                            <div style={{ display: 'flex', gap: '0.5rem', maxWidth: '450px' }}>
                                <input
                                    type="text"
                                    className="form-control"
                                    value={newInvalidTopic}
                                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewInvalidTopic(e.target.value)}
                                    placeholder="Enter forbidden topic (e.g. Gambling)"
                                    onKeyPress={(e: React.KeyboardEvent<HTMLInputElement>) => e.key === 'Enter' && handleAddInvalidTopic()}
                                />
                                <button onClick={handleAddInvalidTopic} className="btn btn-danger" style={{ whiteSpace: 'nowrap' }}>Add Topic</button>
                            </div>
                        </section>

                        <div style={{ display: 'flex', justifyContent: 'flex-start', padding: '0 1.5rem 2rem' }}>
                            <button onClick={handleSaveConfig} disabled={savingConfig} className="btn btn-primary" style={{ minWidth: '200px', boxShadow: '0 4px 6px rgba(0,123,255,0.2)' }}>
                                {savingConfig ? 'Saving...' : 'Save Configuration'}
                            </button>
                        </div>
                    </div>
                ) : (
                    <p style={{ padding: '2rem', textAlign: 'center', color: '#666' }}>Loading Guardrails configuration...</p>
                )}
            </section> */}

            <section className="section-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                    <h2 style={{ margin: 0 }}>Knowledge Base ({products.length} items)</h2>
                    {products.length > 0 && (
                        <button onClick={handleDeleteAll} disabled={loading} className="btn btn-danger" style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}>Delete All</button>
                    )}
                </div>
                {products.length === 0 ? (
                    <p>No documents found in the database.</p>
                ) : (
                    <div className="table-container">
                        <table className="product-table">
                            <thead>
                                <tr>
                                    <th>Category</th>
                                    <th>Question (EN)</th>
                                    <th>Question (AR)</th>
                                    <th style={{ width: '120px' }}>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {products.map((product: Product) => (
                                    <tr key={product.product_id}>
                                        <td><span className="category-badge">{product.category}</span></td>
                                        <td>{product.question_en}</td>
                                        <td className="rtl">{product.question_ar}</td>
                                        <td>
                                            <button onClick={() => openModal(product)} className="action-link action-edit">Edit</button>
                                            <button onClick={() => handleDelete(product.product_id)} className="action-link action-delete">Delete</button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </section>

            {showModal && (
                <div className="modal-overlay">
                    <div className="modal-content">
                        <h2>{currentProduct.product_id ? 'Edit Product' : 'Add New Product'}</h2>
                        <form onSubmit={handleUpsert}>
                            <div className="form-group">
                                <label>Category</label>
                                <input type="text" className="form-control" value={currentProduct.category} onChange={(e: ChangeEvent<HTMLInputElement>) => setCurrentProduct({ ...currentProduct, category: e.target.value })} required />
                            </div>
                            <div className="form-group">
                                <label>English Question</label>
                                <input type="text" className="form-control" value={currentProduct.question_en} onChange={(e: ChangeEvent<HTMLInputElement>) => setCurrentProduct({ ...currentProduct, question_en: e.target.value })} required />
                            </div>
                            <div className="form-group">
                                <label>English Answer</label>
                                <textarea rows={3} className="form-control" value={currentProduct.answer_en} onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setCurrentProduct({ ...currentProduct, answer_en: e.target.value })} required />
                            </div>
                            <div className="form-group">
                                <label>Arabic Question</label>
                                <input type="text" className="form-control rtl" value={currentProduct.question_ar} onChange={(e: ChangeEvent<HTMLInputElement>) => setCurrentProduct({ ...currentProduct, question_ar: e.target.value })} />
                            </div>
                            <div className="form-group">
                                <label>Arabic Answer</label>
                                <textarea rows={3} className="form-control rtl" value={currentProduct.answer_ar} onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setCurrentProduct({ ...currentProduct, answer_ar: e.target.value })} />
                            </div>
                            <div>
                                <div className="change-disclaimer-popup">
                                    <span><svg width="20" height="20" viewBox="0 0 24 24" fill="none"
                                        stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                                        <line x1="12" y1="9" x2="12" y2="13" />
                                        <line x1="12" y1="17" x2="12.01" y2="17" />
                                    </svg></span>
                                    <span>These changes will take effect for users upon their next login.
                                        Any currently active sessions will not be affected until the user logs out.</span>
                                </div>
                            </div>
                            <div className="modal-footer">
                                <button type="button" onClick={() => setShowModal(false)} className="btn btn-secondary">Cancel</button>
                                <button type="submit" disabled={loading} className="btn btn-primary">
                                    {loading ? 'Saving...' : 'Save Product'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
