import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Toast } from '../components/Toast';
import api from '../services/api';
import { getInterviewers, createInterviewer, updateInterviewer, deactivateInterviewer, previewVoice } from '../services/interviewService';

const TABS = {
    LIST: 'list',
    CREATE: 'create',
    EDIT: 'edit',
};

export default function InterviewerManagement() {
    const navigate = useNavigate();
    const [activeTab, setActiveTab] = useState(TABS.LIST);
    const [interviewers, setInterviewers] = useState([]);
    const [loading, setLoading] = useState(false);
    const [toast, setToast] = useState(null);
    const [selectedInterviewer, setSelectedInterviewer] = useState(null);
    const [showInactive, setShowInactive] = useState(false);
    
    // Form state
    const [formData, setFormData] = useState({
        name: '',
        title: '',
        tagline: '',
        description: '',
        personality: '',
        speaking_style: '',
        greeting: '',
        avatar_initials: '',
        accent: 'indigo',
        avatar_url: '',
        voice_id: 'retell-Cimo',
        voice_model: '',
        language_code: 'en-US',
        pace: 0.95,
    });
    
    const [formErrors, setFormErrors] = useState({});
    const [submitting, setSubmitting] = useState(false);
    const [previewingVoice, setPreviewingVoice] = useState(null);

    const accentOptions = [
        { value: 'indigo', label: 'Indigo', color: 'bg-indigo-500' },
        { value: 'violet', label: 'Violet', color: 'bg-violet-500' },
        { value: 'slate', label: 'Slate', color: 'bg-slate-500' },
        { value: 'emerald', label: 'Emerald', color: 'bg-emerald-500' },
        { value: 'rose', label: 'Rose', color: 'bg-rose-500' },
        { value: 'amber', label: 'Amber', color: 'bg-amber-500' },
        { value: 'blue', label: 'Blue', color: 'bg-blue-500' },
        { value: 'purple', label: 'Purple', color: 'bg-purple-500' },
    ];

    const voiceOptions = [
        { id: 'retell-Cimo', name: 'Cimo (Retell)', provider: 'retell', description: 'Professional male voice' },
        { id: 'retell-Jessica', name: 'Jessica (Retell)', provider: 'retell', description: 'Professional female voice' },
    ];

    // Load interviewers on mount and tab change
    useEffect(() => {
        if (activeTab === TABS.LIST) {
            loadInterviewers();
        }
    }, [activeTab, showInactive]);

    const loadInterviewers = async () => {
        setLoading(true);
        try {
            const response = await getInterviewers(showInactive);
            setInterviewers(response.data || []);
        } catch (error) {
            console.error('Failed to load interviewers:', error);
            setToast({ type: 'error', message: 'Failed to load interviewers' });
        } finally {
            setLoading(false);
        }
    };

    const handleCreateInterviewer = async (e) => {
        e.preventDefault();
        
        // Validate
        const errors = validateForm(formData);
        if (Object.keys(errors).length > 0) {
            setFormErrors(errors);
            setToast({ type: 'error', message: 'Please fix the errors in the form' });
            return;
        }
        
        setFormErrors({});
        setSubmitting(true);
        
        try {
            const result = await createInterviewer(formData);
            setToast({ 
                type: 'success', 
                message: `Interviewer "${result.interviewer.name}" created successfully!` 
            });
            resetForm();
            setActiveTab(TABS.LIST);
        } catch (error) {
            console.error('Failed to create interviewer:', error.response?.data || error);
            setToast({ 
                type: 'error', 
                message: error.response?.data?.detail || 'Failed to create interviewer' 
            });
        } finally {
            setSubmitting(false);
        }
    };

    const handleUpdateInterviewer = async (e) => {
        e.preventDefault();
        
        if (!selectedInterviewer) return;
        
        // Validate
        const errors = validateForm(formData, true);
        if (Object.keys(errors).length > 0) {
            setFormErrors(errors);
            setToast({ type: 'error', message: 'Please fix the errors in the form' });
            return;
        }
        
        setFormErrors({});
        setSubmitting(true);
        
        try {
            const result = await updateInterviewer(selectedInterviewer.id, formData);
            setToast({ 
                type: 'success', 
                message: `Interviewer "${result.name}" updated successfully!` 
            });
            setActiveTab(TABS.LIST);
        } catch (error) {
            console.error('Failed to update interviewer:', error);
            setToast({ 
                type: 'error', 
                message: error.response?.data?.detail || 'Failed to update interviewer' 
            });
        } finally {
            setSubmitting(false);
        }
    };

    const handleDeactivateInterviewer = async (interviewer) => {
        const confirmed = window.confirm(
            `Are you sure you want to deactivate "${interviewer.name}"? ` +
            `This will prevent new interviews from using this interviewer, ` +
            `but existing interviews will not be affected.`
        );
        
        if (!confirmed) return;
        
        try {
            await deactivateInterviewer(interviewer.id);
            setToast({ type: 'success', message: `Interviewer "${interviewer.name}" deactivated` });
            loadInterviewers();
        } catch (error) {
            console.error('Failed to deactivate interviewer:', error);
            setToast({ type: 'error', message: 'Failed to deactivate interviewer' });
        }
    };

    const handleEditInterviewer = (interviewer) => {
        setSelectedInterviewer(interviewer);
        setFormData({
            name: interviewer.name,
            title: interviewer.title,
            tagline: interviewer.tagline,
            description: interviewer.description || '',
            personality: interviewer.personality,
            speaking_style: interviewer.speaking_style,
            greeting: interviewer.greeting,
            avatar_initials: interviewer.avatar_initials,
            accent: interviewer.accent,
            avatar_url: interviewer.avatar_url || '',
            voice_id: interviewer.voice_id,
            voice_model: interviewer.voice_model || '',
            language_code: interviewer.language_code,
            pace: interviewer.pace,
        });
        setFormErrors({});
        setActiveTab(TABS.EDIT);
    };

    const handleNewInterviewer = () => {
        resetForm();
        setSelectedInterviewer(null);
        setActiveTab(TABS.CREATE);
    };

    const resetForm = () => {
        setFormData({
            name: '',
            title: '',
            tagline: '',
            description: '',
            personality: '',
            speaking_style: '',
            greeting: '',
            avatar_initials: '',
            accent: 'indigo',
            avatar_url: '',
            voice_id: 'retell-Cimo',
            voice_model: '',
            language_code: 'en-US',
            pace: 0.95,
        });
        setFormErrors({});
        setSelectedInterviewer(null);
    };

    const validateForm = (data, isUpdate = false) => {
        const errors = {};
        
        if (!data.name?.trim()) errors.name = 'Name is required';
        if (!data.title?.trim()) errors.title = 'Title is required';
        if (!data.tagline?.trim()) errors.tagline = 'Tagline is required';
        if (!data.personality?.trim()) errors.personality = 'Personality is required';
        if (!data.speaking_style?.trim()) errors.speaking_style = 'Speaking style is required';
        if (!data.greeting?.trim()) errors.greeting = 'Greeting is required';
        if (!data.avatar_initials?.trim()) errors.avatar_initials = 'Avatar initials are required';
        if (!data.voice_id?.trim()) errors.voice_id = 'Voice is required';
        
        if (data.avatar_initials && data.avatar_initials.length > 10) {
            errors.avatar_initials = 'Avatar initials must be 10 characters or less';
        }
        
        if (data.pace < 0.5 || data.pace > 2.0) {
            errors.pace = 'Pace must be between 0.5 and 2.0';
        }
        
        return errors;
    };

    const handleVoicePreview = async (voiceId) => {
        if (previewingVoice === voiceId) return;
        const voice = voiceOptions.find((option) => option.id === voiceId);
        if (voice?.provider !== 'sarvam') {
            setToast({
                type: 'error',
                message: 'Only Sarvam voices can be previewed here; other providers require their own call integration.',
            });
            return;
        }
        setPreviewingVoice(voiceId);
        
        try {
            await previewVoice(voiceId, `Hello, I'm a preview of the ${voiceId} voice.`);
        } catch (error) {
            console.warn('Voice preview failed:', error);
            setToast({ type: 'error', message: 'Voice preview failed' });
        } finally {
            setPreviewingVoice(null);
        }
    };

    const getAccentColor = (accent) => {
        const option = accentOptions.find(o => o.value === accent);
        return option?.color || 'bg-indigo-500';
    };

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900 font-['Inter'] antialiased">
            {toast && <Toast {...toast} onClose={() => setToast(null)} />}
            
            <div className="min-h-screen bg-slate-50">
                {/* Header */}
                <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
                    <div className="max-w-7xl mx-auto px-6 py-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <h1 className="text-2xl font-bold text-slate-900">Interviewer Management</h1>
                                <p className="text-sm text-slate-500 mt-1">
                                    Create and manage AI interviewers with Retell voice integration
                                </p>
                            </div>
                            {activeTab === TABS.LIST && (
                                <button
                                    onClick={handleNewInterviewer}
                                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-xl transition-colors shadow-sm"
                                >
                                    + Create Interviewer
                                </button>
                            )}
                        </div>
                    </div>
                </header>

                <main className="max-w-7xl mx-auto px-6 py-8">
                    {/* Tab Navigation */}
                    <div className="mb-6 border-b border-slate-200">
                        <nav className="flex gap-8" aria-label="Interviewer management tabs">
                            <button
                                onClick={() => setActiveTab(TABS.LIST)}
                                className={`px-4 py-3 border-b-2 font-semibold text-sm transition-colors ${
                                    activeTab === TABS.LIST
                                        ? 'border-indigo-600 text-indigo-600'
                                        : 'border-transparent text-slate-500 hover:text-slate-700'
                                }`}
                            >
                                All Interviewers ({interviewers.length})
                            </button>
                            <button
                                onClick={() => setActiveTab(TABS.CREATE)}
                                className={`px-4 py-3 border-b-2 font-semibold text-sm transition-colors ${
                                    activeTab === TABS.CREATE
                                        ? 'border-indigo-600 text-indigo-600'
                                        : 'border-transparent text-slate-500 hover:text-slate-700'
                                }`}
                            >
                                Create New
                            </button>
                        </nav>
                    </div>

                    {/* Content */}
                    {activeTab === TABS.LIST && (
                        <div className="space-y-6">
                            {/* Filters */}
                            <div className="bg-white border border-slate-200 rounded-2xl p-4 flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
                                <label className="flex items-center gap-2 cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={showInactive}
                                        onChange={(e) => setShowInactive(e.target.checked)}
                                        className="w-4 h-4 text-indigo-600 border-slate-300 rounded focus:ring-indigo-500 focus:ring-2"
                                    />
                                    <span className="text-sm font-medium text-slate-700">Show inactive interviewers</span>
                                </label>
                                <div className="text-sm text-slate-500">
                                    {interviewers.filter(i => i.is_active).length} active, {interviewers.filter(i => !i.is_active).length} inactive
                                </div>
                            </div>

                            {loading ? (
                                <div className="bg-white border border-slate-200 rounded-2xl p-8 text-center">
                                    <div className="w-8 h-8 border-4 border-slate-200 border-t-indigo-500 rounded-full animate-spin mx-auto mb-4"></div>
                                    <p className="text-slate-500">Loading interviewers...</p>
                                </div>
                            ) : interviewers.length === 0 ? (
                                <div className="bg-white border border-slate-200 rounded-2xl p-12 text-center">
                                    <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl">🎤</div>
                                    <h3 className="text-lg font-semibold text-slate-900 mb-2">No interviewers found</h3>
                                    <p className="text-slate-500 mb-6">Create your first dynamic interviewer to get started</p>
                                    <button
                                        onClick={handleNewInterviewer}
                                        className="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-xl transition-colors shadow-sm"
                                    >
                                        Create Interviewer
                                    </button>
                                </div>
                            ) : (
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    {interviewers
                                        .filter(i => showInactive || i.is_active)
                                        .map((interviewer) => (
                                            <div
                                                key={interviewer.id}
                                                className={`bg-white border rounded-2xl p-6 transition-all hover:shadow-lg ${
                                                    !interviewer.is_active
                                                        ? 'border-slate-200 bg-slate-50 opacity-75'
                                                        : 'border-slate-200 hover:border-indigo-300'
                                                }`}
                                            >
                                                <div className="flex items-start justify-between gap-4 mb-4">
                                                    <div className={`w-14 h-14 rounded-2xl flex items-center justify-center text-white font-bold text-xl shrink-0 ${getAccentColor(interviewer.accent)}`}>
                                                        {interviewer.avatar_initials}
                                                    </div>
                                                    <div className="flex flex-col items-end gap-1">
                                                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                                                            interviewer.is_dynamic
                                                                ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                                                                : 'bg-slate-100 text-slate-700 border border-slate-200'
                                                        }`}>
                                                            {interviewer.is_dynamic ? 'Dynamic' : 'Static'}
                                                        </span>
                                                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                                                            interviewer.is_active
                                                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                                                : 'bg-slate-100 text-slate-700 border border-slate-200'
                                                        }`}>
                                                            {interviewer.is_active ? 'Active' : 'Inactive'}
                                                        </span>
                                                    </div>
                                                </div>
                                                
                                                <h3 className="font-bold text-slate-900 text-lg mb-1">{interviewer.name}</h3>
                                                <p className="text-sm text-slate-600 mb-2">{interviewer.title}</p>
                                                <p className="text-sm text-slate-500 line-clamp-2 mb-4">{interviewer.tagline}</p>
                                                
                                                <div className="flex items-center gap-2 text-xs text-slate-500 mb-4">
                                                    <span className="flex items-center gap-1">
                                                        <span className="w-2 h-2 rounded-full bg-green-500"></span>
                                                        Voice: {interviewer.voice_id}
                                                    </span>
                                                </div>
                                                
                                                {interviewer.is_dynamic && (
                                                    <div className="pt-4 border-t border-slate-100 flex gap-2">
                                                        <button
                                                            onClick={() => handleEditInterviewer(interviewer)}
                                                            className="flex-1 px-3 py-2 text-sm font-semibold text-indigo-600 hover:text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-xl transition-colors"
                                                        >
                                                            Edit
                                                        </button>
                                                        <button
                                                            onClick={() => handleDeactivateInterviewer(interviewer)}
                                                            disabled={!interviewer.is_active}
                                                            className="flex-1 px-3 py-2 text-sm font-semibold text-red-600 hover:text-red-700 bg-red-50 hover:bg-red-100 rounded-xl transition-colors disabled:opacity-50"
                                                        >
                                                            {interviewer.is_active ? 'Deactivate' : 'Activated'}
                                                        </button>
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                </div>
                            )}
                        </div>
                    )}

                    {activeTab === TABS.CREATE && (
                        <InterviewerForm
                            formData={formData}
                            formErrors={formErrors}
                            setFormData={setFormData}
                            voiceOptions={voiceOptions}
                            accentOptions={accentOptions}
                            onSubmit={handleCreateInterviewer}
                            onCancel={() => setActiveTab(TABS.LIST)}
                            submitting={submitting}
                            previewingVoice={previewingVoice}
                            onVoicePreview={handleVoicePreview}
                            isEdit={false}
                        />
                    )}

                    {activeTab === TABS.EDIT && selectedInterviewer && (
                        <InterviewerForm
                            formData={formData}
                            formErrors={formErrors}
                            setFormData={setFormData}
                            voiceOptions={voiceOptions}
                            accentOptions={accentOptions}
                            onSubmit={handleUpdateInterviewer}
                            onCancel={() => { setActiveTab(TABS.LIST); setSelectedInterviewer(null); }}
                            submitting={submitting}
                            previewingVoice={previewingVoice}
                            onVoicePreview={handleVoicePreview}
                            isEdit={true}
                            interviewerName={selectedInterviewer.name}
                        />
                    )}
                </main>
            </div>
        </div>
    );
}

// Interviewer Form Component
function InterviewerForm({
    formData,
    formErrors,
    setFormData,
    voiceOptions,
    accentOptions,
    onSubmit,
    onCancel,
    submitting,
    previewingVoice,
    onVoicePreview,
    isEdit,
    interviewerName,
}) {
    const selectedVoiceProvider = voiceOptions.find(
        (voice) => voice.id === formData.voice_id
    )?.provider;

    const handleChange = (field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
        // Clear error when user starts typing
        if (formErrors[field]) {
            // We can't directly modify formErrors here, but the parent will handle it
        }
    };

    return (
        <div className="bg-white border border-slate-200 rounded-3xl p-8 max-w-3xl mx-auto">
            <div className="mb-8 flex items-center justify-between">
                <h2 className="text-xl font-bold text-slate-900">
                    {isEdit ? `Edit ${interviewerName || 'Interviewer'}` : 'Create New Interviewer'}
                </h2>
                <button
                    onClick={onCancel}
                    className="text-sm text-slate-500 hover:text-slate-700 font-medium"
                >
                    ← Back to List
                </button>
            </div>

            <form onSubmit={onSubmit} className="space-y-6">
                {/* Basic Information */}
                <fieldset className="border border-slate-200 rounded-2xl p-6">
                    <legend className="text-sm font-bold text-slate-900 mb-4">Basic Information</legend>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1.5">
                                Name <span className="text-red-500">*</span>
                            </label>
                            <input
                                type="text"
                                value={formData.name}
                                onChange={(e) => handleChange('name', e.target.value)}
                                placeholder="e.g., Alex Chen"
                                className={`w-full px-4 py-3 bg-slate-50 border rounded-xl text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                                    formErrors.name ? 'border-red-500' : 'border-slate-300'
                                }`}
                            />
                            {formErrors.name && <p className="mt-1 text-sm text-red-500">{formErrors.name}</p>}
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1.5">
                                Title <span className="text-red-500">*</span>
                            </label>
                            <input
                                type="text"
                                value={formData.title}
                                onChange={(e) => handleChange('title', e.target.value)}
                                placeholder="e.g., Senior Backend Engineer"
                                className={`w-full px-4 py-3 bg-slate-50 border rounded-xl text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                                    formErrors.title ? 'border-red-500' : 'border-slate-300'
                                }`}
                            />
                            {formErrors.title && <p className="mt-1 text-sm text-red-500">{formErrors.title}</p>}
                        </div>
                        <div className="md:col-span-2">
                            <label className="block text-sm font-medium text-slate-700 mb-1.5">
                                Tagline <span className="text-red-500">*</span>
                            </label>
                            <input
                                type="text"
                                value={formData.tagline}
                                onChange={(e) => handleChange('tagline', e.target.value)}
                                placeholder="e.g., Expert in distributed systems and cloud architecture"
                                className={`w-full px-4 py-3 bg-slate-50 border rounded-xl text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                                    formErrors.tagline ? 'border-red-500' : 'border-slate-300'
                                }`}
                            />
                            {formErrors.tagline && <p className="mt-1 text-sm text-red-500">{formErrors.tagline}</p>}
                        </div>
                        <div className="md:col-span-2">
                            <label className="block text-sm font-medium text-slate-700 mb-1.5">
                                Description
                            </label>
                            <textarea
                                value={formData.description}
                                onChange={(e) => handleChange('description', e.target.value)}
                                rows={3}
                                placeholder="Optional description for admin reference"
                                className="w-full px-4 py-3 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
                            />
                        </div>
                    </div>
                </fieldset>

                {/* Personality & Style */}
                <fieldset className="border border-slate-200 rounded-2xl p-6">
                    <legend className="text-sm font-bold text-slate-900 mb-4">Personality & Speaking Style</legend>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1.5">
                                Personality <span className="text-red-500">*</span>
                            </label>
                            <textarea
                                value={formData.personality}
                                onChange={(e) => handleChange('personality', e.target.value)}
                                rows={3}
                                placeholder="e.g., Calm, analytical, encouraging, direct but kind"
                                className={`w-full px-4 py-3 bg-slate-50 border rounded-xl text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                                    formErrors.personality ? 'border-red-500' : 'border-slate-300'
                                }`}
                            />
                            {formErrors.personality && <p className="mt-1 text-sm text-red-500">{formErrors.personality}</p>}
                            <p className="mt-1 text-xs text-slate-500">Comma-separated traits (e.g., calm, analytical, encouraging)</p>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1.5">
                                Speaking Style <span className="text-red-500">*</span>
                            </label>
                            <textarea
                                value={formData.speaking_style}
                                onChange={(e) => handleChange('speaking_style', e.target.value)}
                                rows={3}
                                placeholder="e.g., Concise and technically precise, uses analogies"
                                className={`w-full px-4 py-3 bg-slate-50 border rounded-xl text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                                    formErrors.speaking_style ? 'border-red-500' : 'border-slate-300'
                                }`}
                            />
                            {formErrors.speaking_style && <p className="mt-1 text-sm text-red-500">{formErrors.speaking_style}</p>}
                        </div>
                    </div>
                    <div className="mt-6">
                        <label className="block text-sm font-medium text-slate-700 mb-1.5">
                            Greeting <span className="text-red-500">*</span>
                        </label>
                        <textarea
                            value={formData.greeting}
                            onChange={(e) => handleChange('greeting', e.target.value)}
                            rows={2}
                            placeholder="e.g., Hi, I'm {name}. Thanks for making the time today — let's start with a quick introduction."
                            className={`w-full px-4 py-3 bg-slate-50 border rounded-xl text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                                formErrors.greeting ? 'border-red-500' : 'border-slate-300'
                            }`}
                        />
                        {formErrors.greeting && <p className="mt-1 text-sm text-red-500">{formErrors.greeting}</p>}
                        <p className="mt-1 text-xs text-slate-500">Use {name} as placeholder for interviewer's name</p>
                    </div>
                </fieldset>

                {/* Avatar & Visual */}
                <fieldset className="border border-slate-200 rounded-2xl p-6">
                    <legend className="text-sm font-bold text-slate-900 mb-4">Avatar & Visual</legend>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1.5">
                                Avatar Initials <span className="text-red-500">*</span>
                            </label>
                            <input
                                type="text"
                                value={formData.avatar_initials}
                                onChange={(e) => handleChange('avatar_initials', e.target.value.toUpperCase().slice(0, 10))}
                                maxLength={10}
                                placeholder="e.g., AC"
                                className={`w-full px-4 py-3 bg-slate-50 border rounded-xl text-slate-900 font-medium text-center uppercase focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                                    formErrors.avatar_initials ? 'border-red-500' : 'border-slate-300'
                                }`}
                            />
                            {formErrors.avatar_initials && <p className="mt-1 text-sm text-red-500">{formErrors.avatar_initials}</p>}
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1.5">
                                Accent Color
                            </label>
                            <select
                                value={formData.accent}
                                onChange={(e) => handleChange('accent', e.target.value)}
                                className="w-full px-4 py-3 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
                            >
                                {accentOptions.map(opt => (
                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1.5">
                                Avatar URL (optional)
                            </label>
                            <input
                                type="url"
                                value={formData.avatar_url}
                                onChange={(e) => handleChange('avatar_url', e.target.value)}
                                placeholder="https://example.com/avatar.png"
                                className="w-full px-4 py-3 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
                            />
                        </div>
                    </div>
                </fieldset>

                {/* Voice Configuration */}
                <fieldset className="border border-slate-200 rounded-2xl p-6">
                    <legend className="text-sm font-bold text-slate-900 mb-4 flex items-center justify-between">
                        Voice Configuration
                        <span className="text-xs text-slate-500">Powered by Retell + Sarvam</span>
                    </legend>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1.5">
                                Voice <span className="text-red-500">*</span>
                            </label>
                            <div className="relative">
                                <select
                                    value={formData.voice_id}
                                    onChange={(e) => handleChange('voice_id', e.target.value)}
                                    className={`w-full px-4 py-3 bg-slate-50 border rounded-xl text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 pr-12 ${
                                        formErrors.voice_id ? 'border-red-500' : 'border-slate-300'
                                    }`}
                                >
                                    {voiceOptions.map(voice => (
                                        <option key={voice.id} value={voice.id}>
                                            {voice.name} ({voice.provider})
                                        </option>
                                    ))}
                                </select>
                                <button
                                    type="button"
                                    onClick={() => onVoicePreview(formData.voice_id)}
                                    disabled={selectedVoiceProvider !== 'sarvam' || previewingVoice === formData.voice_id || submitting}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 px-3 py-1.5 text-xs font-bold rounded-lg transition-colors flex items-center gap-1.5 bg-slate-100 text-slate-600 hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    <span className={`w-3 h-3 rounded-full animate-pulse ${previewingVoice === formData.voice_id ? 'bg-indigo-500' : 'bg-slate-300'}`}></span>
                                    {previewingVoice === formData.voice_id ? 'Playing...' : selectedVoiceProvider === 'sarvam' ? 'Preview' : 'Interview only'}
                                </button>
                            </div>
                            {formErrors.voice_id && <p className="mt-1 text-sm text-red-500">{formErrors.voice_id}</p>}
                            {selectedVoiceProvider === 'retell' && (
                                <p className="mt-1 text-xs text-slate-500">
                                    Retell audio is played in the interview and requires the Retell backend configuration.
                                </p>
                            )}
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1.5">
                                Voice Model (optional)
                            </label>
                            <input
                                type="text"
                                value={formData.voice_model}
                                onChange={(e) => handleChange('voice_model', e.target.value)}
                                placeholder="e.g., bulbul:v3"
                                className="w-full px-4 py-3 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1.5">
                                Language Code
                            </label>
                            <input
                                type="text"
                                value={formData.language_code}
                                onChange={(e) => handleChange('language_code', e.target.value)}
                                placeholder="en-US"
                                className="w-full px-4 py-3 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1.5">
                                Pace <span className="text-slate-500">(0.5 - 2.0)</span>
                            </label>
                            <input
                                type="number"
                                value={formData.pace}
                                onChange={(e) => handleChange('pace', parseFloat(e.target.value) || 0.95)}
                                step={0.05}
                                min={0.5}
                                max={2.0}
                                className={`w-full px-4 py-3 bg-slate-50 border rounded-xl text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                                    formErrors.pace ? 'border-red-500' : 'border-slate-300'
                                }`}
                            />
                            {formErrors.pace && <p className="mt-1 text-sm text-red-500">{formErrors.pace}</p>}
                        </div>
                    </div>
                    
                    {/* Voice Preview Section */}
                    <div className="mt-6 p-4 bg-slate-50 rounded-xl">
                        <p className="text-sm text-slate-600 mb-3">Test the selected voice:</p>
                        <div className="flex flex-wrap gap-2">
                            {voiceOptions.slice(0, 4).map(voice => (
                                <button
                                    key={voice.id}
                                    type="button"
                                    onClick={() => onVoicePreview(voice.id)}
                                    disabled={previewingVoice === voice.id || submitting}
                                    className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 ${
                                        previewingVoice === voice.id
                                            ? 'bg-indigo-600 text-white'
                                            : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
                                    }`}
                                >
                                    <span className={`w-3 h-3 rounded-full animate-pulse ${previewingVoice === voice.id ? 'bg-white' : 'bg-slate-300'}`}></span>
                                    {voice.name}
                                </button>
                            ))}
                        </div>
                    </div>
                </fieldset>

                {/* Submit Buttons */}
                <div className="flex flex-col sm:flex-row gap-4 justify-end pt-4 border-t border-slate-200">
                    <button
                        type="button"
                        onClick={onCancel}
                        className="flex-1 sm:flex-none px-6 py-3 text-sm font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        type="submit"
                        disabled={submitting}
                        className="flex-1 sm:flex-none px-6 py-3 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-400 rounded-xl transition-colors flex items-center justify-center gap-2"
                    >
                        {submitting && (
                            <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                            </svg>
                        )}
                        {isEdit ? 'Update Interviewer' : 'Create Interviewer'}
                    </button>
                </div>
            </form>
        </div>
    );
}

export { InterviewerManagement };