import React, { useState, useEffect, ChangeEvent, FormEvent, useRef } from 'react';
import axios from 'axios';
import { Endpoints } from '../api/endpoints';
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

interface GuardrailsConfig {
    is_safe_input: boolean;
    enforce_anonymous_mode: boolean;
    block_financial_advisory: boolean;
    escalation_trigger: boolean;
    restrict_to_topic: boolean;
    detect_pii_input: boolean;
    secrets_present_input: boolean;
    toxic_language: boolean;
    gibberish_text: boolean;
    detect_pii_output: boolean;
    secrets_present_output: boolean;
    is_safe_output: boolean;
    valid_topics: string[];
}

interface BackofficeProps {
    sessionId: string;
}

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

    const [config, setConfig] = useState<GuardrailsConfig | null>(null);
    const [savingConfig, setSavingConfig] = useState(false);
    const [newTopic, setNewTopic] = useState('');

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
        fetchConfig();
    }, []);

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
        if (!window.confirm(`Are you sure you want to delete this product?`)) return;
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
        if (!window.confirm("ARE YOU SURE? This will permanently delete ALL products from the database.")) return;
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


    return (
        <div className="backoffice-container">
            <header className="backoffice-header">
                <h1>Document Backoffice</h1>
                <div style={{ display: 'flex', gap: '1rem' }}>
                    <button onClick={() => openModal()} className="btn btn-success">+ Add New</button>
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

            <section className="section-card">
                <h3>Guardrails Configuration</h3>
                <p style={{ marginBottom: '1rem', fontSize: '0.9rem', color: '#555' }}>Toggle validation rules on or off dynamically.</p>

                {config ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>

                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
                            {Object.entries(config)
                                .filter(([key]) => key !== 'valid_topics')
                                .map(([key, value]) => (
                                    <div key={key} className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', margin: 0 }}>
                                        <label className="switch" style={{ position: 'relative', display: 'inline-block', width: '40px', height: '20px' }}>
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
                                                    position: 'absolute', content: '""', height: '16px', width: '16px',
                                                    left: value ? '22px' : '2px', bottom: '2px', backgroundColor: 'white',
                                                    transition: '.4s', borderRadius: '50%'
                                                }} />
                                            </span>
                                        </label>
                                        <span style={{ fontSize: '0.9rem', textTransform: 'capitalize' }}>
                                            {key.split('_').join(' ')}
                                        </span>
                                    </div>
                                ))}
                        </div>

                        <div>
                            <h4>Dynamic Topics</h4>
                            <p style={{ fontSize: '0.85rem', color: '#666', marginBottom: '0.5rem' }}>These topics are permitted by the Restrict To Topic validation when enabled.</p>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
                                {config.valid_topics.map((topic: string) => (
                                    <span key={topic} style={{ background: '#e1f5fe', color: '#0277bd', padding: '0.3rem 0.6rem', borderRadius: '16px', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        {topic}
                                        <button onClick={() => handleRemoveTopic(topic)} style={{ background: 'none', border: 'none', color: '#0277bd', cursor: 'pointer', outline: 'none', padding: 0, fontSize: '1rem', lineHeight: 1 }}>&times;</button>
                                    </span>
                                ))}
                            </div>
                            <div style={{ display: 'flex', gap: '0.5rem', maxWidth: '400px' }}>
                                <input
                                    type="text"
                                    className="form-control"
                                    value={newTopic}
                                    onChange={e => setNewTopic(e.target.value)}
                                    placeholder="Enter new topic"
                                    onKeyPress={(e: React.KeyboardEvent<HTMLInputElement>) => e.key === 'Enter' && handleAddTopic()}
                                />
                                <button onClick={handleAddTopic} className="btn btn-secondary">Add</button>
                            </div>
                        </div>

                        <button onClick={handleSaveConfig} disabled={savingConfig} className="btn btn-primary" style={{ alignSelf: 'flex-start' }}>
                            {savingConfig ? 'Saving...' : 'Save Configuration'}
                        </button>
                    </div>
                ) : (
                    <p>Loading configuration...</p>
                )}
            </section>

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
