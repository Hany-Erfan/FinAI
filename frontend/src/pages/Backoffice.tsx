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
    }, []);

    const fetchProducts = async () => {
        try {
            const res = await axios.get(Endpoints.BACKOFFICE_PRODUCTS, axiosConfig);
            if (res.data) {
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

    return (
        <div className="backoffice-container">
            <header className="backoffice-header">
                <h1>Document Backoffice</h1>
                <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                    {/* <button onClick={() => navigate('/guardrails')} className="btn btn-primary">Guardrails Management</button> */}
                    <button onClick={() => navigate('/analysis-dashboard')} className="btn btn-primary">Analysis Dashboard</button>
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

            <section className="section-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                    <h2 style={{ margin: 0 }}>Knowledge Base Products ({products.length})</h2>
                    <button onClick={handleDeleteAll} className="btn btn-danger" style={{ fontSize: '0.8rem' }}>Delete All Products</button>
                </div>

                <div className="table-container">
                    <table className="product-table">
                        <thead>
                            <tr>
                                <th>Category</th>
                                <th>Question (EN)</th>
                                <th>Answer (EN)</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {products.length === 0 ? (
                                <tr>
                                    <td colSpan={4} style={{ textAlign: 'center', padding: '2rem', color: '#666' }}>No products found in the database.</td>
                                </tr>
                            ) : (
                                products.map((p) => (
                                    <tr key={p.product_id}>
                                        <td data-label="Category"><span className="category-badge">{p.category}</span></td>
                                        <td data-label="Question">{p.question_en}</td>
                                        <td data-label="Answer">{p.answer_en.substring(0, 80)}...</td>
                                        <td data-label="Actions">
                                            <div className="action-buttons">
                                                <button onClick={() => openModal(p)} className="btn btn-secondary btn-sm">Edit</button>
                                                <button onClick={() => handleDelete(p.product_id)} className="btn btn-danger btn-sm">Delete</button>
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </section>

            {showModal && (
                <div className="modal-overlay">
                    <div className="modal-content">
                        <h2>{currentProduct.product_id ? 'Edit Product' : 'Add New Product'}</h2>
                        <form onSubmit={handleUpsert}>
                            <div className="form-grid">
                                <div className="form-group">
                                    <label>Category</label>
                                    <select
                                        className="form-control"
                                        value={currentProduct.category}
                                        onChange={(e) => setCurrentProduct({ ...currentProduct, category: e.target.value })}
                                        required
                                    >
                                        <option value="General">General</option>
                                        <option value="Accounts">Accounts</option>
                                        <option value="Cards">Cards</option>
                                        <option value="Loans">Loans</option>
                                        <option value="Investments">Investments</option>
                                        <option value="Digital Banking">Digital Banking</option>
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label>Question (English)</label>
                                    <textarea
                                        className="form-control"
                                        value={currentProduct.question_en}
                                        onChange={(e) => setCurrentProduct({ ...currentProduct, question_en: e.target.value })}
                                        required
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Answer (English)</label>
                                    <textarea
                                        className="form-control"
                                        value={currentProduct.answer_en}
                                        onChange={(e) => setCurrentProduct({ ...currentProduct, answer_en: e.target.value })}
                                        required
                                        style={{ height: '100px' }}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Question (Arabic)</label>
                                    <textarea
                                        className="form-control"
                                        value={currentProduct.question_ar}
                                        onChange={(e) => setCurrentProduct({ ...currentProduct, question_ar: e.target.value })}
                                        required
                                        dir="rtl"
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Answer (Arabic)</label>
                                    <textarea
                                        className="form-control"
                                        value={currentProduct.answer_ar}
                                        onChange={(e) => setCurrentProduct({ ...currentProduct, answer_ar: e.target.value })}
                                        required
                                        dir="rtl"
                                        style={{ height: '100px' }}
                                    />
                                </div>
                            </div>
                            <div className="modal-actions">
                                <button type="button" onClick={() => setShowModal(false)} className="btn btn-secondary" disabled={loading}>Cancel</button>
                                <button type="submit" className="btn btn-primary" disabled={loading}>
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
