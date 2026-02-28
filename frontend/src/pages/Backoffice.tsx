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
