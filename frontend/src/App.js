import React, { useState, useEffect, useRef } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import axios from 'axios';
import 'bootstrap/dist/css/bootstrap.min.css';
import QueryPage from './pages/QueryPage';
import ResultsPage from './pages/ResultsPage';
import AnalysisPage from './pages/AnalysisPage';
import WarehousePage from './pages/WarehousePage';
import StatusBanner from './components/StatusBanner';

export const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5001';

function App() {
    const [status, setStatus] = useState('idle');
    const [message, setMessage] = useState('Welcome! Configure your query and start the process.');
    const [resultsReadyKey, setResultsReadyKey] = useState(null);
    const intervalRef = useRef(null);

    const prepareResultsForNewTab = async () => {
        setMessage("Loading results page 1...");
        try {
            const firstPageResponse = await axios.get(`${API_BASE_URL}/api/results?page=1&per_page=50`);
            const { papers: firstPagePapers, total_papers } = firstPageResponse.data;
            
            let allPapers = [...firstPagePapers];
            const totalPages = Math.ceil(total_papers / 50);

            for (let page = 2; page <= totalPages; page++) {
                setMessage(`Loading results... (${allPapers.length} / ${total_papers})`);
                const response = await axios.get(`${API_BASE_URL}/api/results?page=${page}&per_page=50`);
                allPapers.push(...response.data.papers);
            }

            const sessionKey = `results_${Date.now()}`;
            localStorage.setItem(sessionKey, JSON.stringify(allPapers));
            
            setResultsReadyKey(sessionKey);
            setStatus('review_ready');
            setMessage(`All ${total_papers} results loaded.`);

        } catch (error) {
            console.error("Failed to fetch all results:", error);
            setMessage("Error loading results from backend.");
            setStatus('error');
        }
    };

    const handleViewResults = (sessionKey) => {
        window.open(`/results?sessionKey=${sessionKey}`, '_blank');
        setResultsReadyKey(null);
        setStatus('idle');
    };

    const fetchStatus = async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/api/status`);
            const { status: newStatus, message: newMessage } = response.data;
            
            if (status !== 'review_ready') {
                setStatus(newStatus);
                setMessage(newMessage);
            }

            if (newStatus === 'review_ready') {
                stopPolling();
                prepareResultsForNewTab();
            }
            if ([ 'success', 'error', 'idle'].includes(newStatus)){
                stopPolling();
            }
        } catch (error) {
            // Suppress polling errors
        }
    };

    const startPolling = () => {
        if (intervalRef.current) clearInterval(intervalRef.current);
        setResultsReadyKey(null);
        intervalRef.current = setInterval(fetchStatus, 2000);
    };

    const stopPolling = () => {
        clearInterval(intervalRef.current);
    };

    useEffect(() => {
        return () => clearInterval(intervalRef.current);
    }, []);

    const sharedProps = {
        status,
        setStatus,
        message,
        setMessage,
        startPolling
    };

    return (
        <div className="container mt-4 mb-4">
            <StatusBanner 
                status={status} 
                message={message} 
                resultsReadyKey={resultsReadyKey}
                onViewResults={handleViewResults}
            />
            <Routes>
                <Route path="/" element={<QueryPage {...sharedProps} />} />
                <Route path="/results" element={<ResultsPage {...sharedProps} />} />
                <Route path="/analysis/:paperId" element={<AnalysisPage />} />
                <Route path="/warehouse" element={<WarehousePage />} />
            </Routes>
        </div>
    );
}

const AppWrapper = () => (
    <Router>
        <App />
    </Router>
);

export default AppWrapper;