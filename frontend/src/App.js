import React, {useEffect, useState} from 'react';
import axios from 'axios';
import 'bootstrap/dist/css/bootstrap.min.css';
import {Accordion, Alert, Button, Card, Col, Container, Dropdown, Form, Nav, Navbar, Row, Table} from 'react-bootstrap';
import {
    AiOutlineBulb,
    AiOutlineCloudUpload,
    AiOutlineEdit,
    AiOutlineFileAdd,
    AiOutlineFileSearch,
    AiOutlinePlusCircle,
    AiOutlineSave,
} from 'react-icons/ai';
import {toast, ToastContainer} from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import './styles.css';

const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://192.168.1.3:8000';

const App = () => {
    const [files, setFiles] = useState([]);
    const [dois, setDois] = useState('');
    const [data, setData] = useState([]);
    const [error, setError] = useState('');
    const [editable, setEditable] = useState(null);
    const [userFolder, setUserFolder] = useState(localStorage.getItem('userFolder') || '');
    const [userName, setUserName] = useState(localStorage.getItem('userName') || '');
    const [topic, setTopic] = useState(localStorage.getItem('topic') || '');
    const [topics, setTopics] = useState([]);
    const [darkMode, setDarkMode] = useState(false);
    const [highlightedTopics, setHighlightedTopics] = useState([]);
    const [newTopic, setNewTopic] = useState('');
    const [isAddingTopic, setIsAddingTopic] = useState(false);
    const [viewAllTopics, setViewAllTopics] = useState(false); // New state for "All Topics" view
    const [allTopicsData, setAllTopicsData] = useState([]); // State to hold all topics' data

    useEffect(() => {
        if (userFolder && topic) {
            fetchData(userFolder, topic);
        } else if (userFolder) {
            fetchTopics(userFolder);
        }
    }, [userFolder, topic]);

    const fetchData = async (folder, topic) => {
        try {
            const response = await axios.get(`${backendUrl}/existing_data`, {
                params: {
                    user_folder: folder,
                    topic: topic
                }
            });
            setData(response.data);
        } catch (error) {
            setError('Error fetching existing data');
        }
    };

    const fetchTopics = async (folder) => {
        try {
            const response = await axios.get(`${backendUrl}/fetch_topics`, {params: {user_folder: folder}});
            setTopics(response.data.topics);
        } catch (error) {
            setError('Error fetching topics');
        }
    };

    const fetchAllTopicsData = async () => {
        try {
            const allData = [];
            for (const topicName of topics) {
                const response = await axios.get(`${backendUrl}/existing_data`, {
                    params: {
                        user_folder: userFolder,
                        topic: topicName
                    }
                });
                allData.push({topic: topicName, data: response.data});
            }
            setAllTopicsData(allData);
        } catch (error) {
            toast.error('An error occurred while fetching all topics data.');
        }
    };

    const handleFileChange = (event) => {
        setFiles(event.target.files);
    };

    const handleDoisChange = (event) => {
        setDois(event.target.value);
    };

    const handleFileSubmit = async (event) => {
        event.preventDefault();
        if (!files.length || !userFolder || !topic) return;

        const formData = new FormData();
        for (const file of files) {
            formData.append('files', file);
        }

        try {
            const response = await axios.post(`${backendUrl}/parse_pdfs`, formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
                params: {user_folder: userFolder, topic: topic},
            });
            setData([...data, ...response.data]);
            toast.success('PDFs uploaded and parsed successfully!');
        } catch (error) {
            toast.error('An error occurred while processing the PDFs.');
        }
    };

    const handleDoisSubmit = async (event) => {
        event.preventDefault();
        if (!userFolder || !topic) return;
        const doiList = dois.split(',').map(doi => doi.trim());
        try {
            const response = await axios.post(`${backendUrl}/fetch_by_dois`, doiList, {
                params: {
                    user_folder: userFolder,
                    topic: topic
                }
            });
            setData([...data, ...response.data]);
            toast.success('DOIs fetched and parsed successfully!');
        } catch (error) {
            toast.error('An error occurred while fetching data for the DOIs.');
        }
    };

    const handleEdit = (index) => {
        setEditable(index);
    };

    const handleSave = async (index) => {
        try {
            const updatedEntry = data[index];
            await axios.post(`${backendUrl}/update_entry`, updatedEntry, {
                params: {
                    user_folder: userFolder,
                    topic: topic
                }
            });
            toast.success('Entry updated successfully!');
            setEditable(null);
        } catch (error) {
            toast.error('An error occurred while updating the entry.');
        }
    };

    const handleDelete = async (index) => {
        if (window.confirm("Are you sure you want to delete this entry?")) {
            try {
                const entry = data[index];
                await axios.delete(`${backendUrl}/delete_entry`, {
                    data: {no: entry.SL_NO},
                    params: {user_folder: userFolder, topic: topic}
                });
                setData(data.filter((_, i) => i !== index));
                toast.success('Entry deleted successfully!');
            } catch (error) {
                toast.error('An error occurred while deleting the entry.');
            }
        }
    };

    const handleChange = (index, field, value) => {
        const updatedData = [...data];
        updatedData[index][field] = value;
        setData(updatedData);
    };

    const handleGoogleSignIn = () => {
        window.location.href = `${backendUrl}/authorize`;
    };

    const handleTopicSelect = (selectedTopic) => {
        setTopic(selectedTopic);
        setViewAllTopics(false);  // Reset view when selecting a single topic
        localStorage.setItem('topic', selectedTopic);
        fetchData(userFolder, selectedTopic);
    };

    const handleAddTopic = async () => {
        if (!isAddingTopic) {
            setIsAddingTopic(true);
            return;
        }

        if (!newTopic) {
            toast.error('Please enter a topic name.');
            return;
        }

        if (topics.includes(newTopic)) {
            toast.error('A topic with this name already exists.');
            return;
        }

        try {
            setTopics([...topics, newTopic]);
            handleTopicSelect(newTopic);
            setNewTopic('');
            setIsAddingTopic(false);
        } catch (error) {
            toast.error('An error occurred while adding the new topic.');
        }
    };

    const toggleDarkMode = () => {
        setDarkMode(!darkMode);
        document.body.classList.toggle('dark-mode');
    };

    useEffect(() => {
        const query = new URLSearchParams(window.location.search);
        const user_email = query.get('user_email');
        const folder_id = query.get('folder_id');
        if (user_email) {
            const username = user_email.split('@')[0];
            setUserName(username);
            localStorage.setItem('userName', username);
            setUserFolder(folder_id);
            localStorage.setItem('userFolder', folder_id);
            fetchTopics(folder_id);
        }
    }, []);

    const handleDOISearch = async () => {
        try {
            const results = [];
            const highlighted = [];
            for (const topicName of topics) {
                const response = await axios.get(`${backendUrl}/existing_data`, {
                    params: {
                        user_folder: userFolder,
                        topic: topicName
                    }
                });
                const foundEntry = response.data.find(entry => entry.DOI === dois);
                if (foundEntry) {
                    results.push(topicName);
                    highlighted.push(topicName);  // Add the topic to the highlighted list
                }
            }
            setHighlightedTopics(highlighted);  // Update highlighted topics

            if (results.length > 0) {
                toast.success(`DOI found in topics: ${results.join(', ')}`);

                // Clear the highlight after 30 seconds
                setTimeout(() => {
                    setHighlightedTopics([]);
                }, 30000);
            } else {
                toast.error('DOI not found in any topic.');
            }
        } catch (error) {
            toast.error('An error occurred while searching for the DOI.');
        }
    };

    const handleViewAllTopics = async () => {
        setViewAllTopics(true);
        await fetchAllTopicsData();
    };

    return (
        <>
            <Navbar bg="dark" variant="dark" expand="lg">
                <Container>
                    <Navbar.Brand href="#" onClick={() => { setTopic(''); setViewAllTopics(false); }}>
                        Research Manager
                    </Navbar.Brand>
                    <Navbar.Toggle aria-controls="basic-navbar-nav"/>
                    <Navbar.Collapse id="basic-navbar-nav" className="justify-content-end">
                        {userName && (
                            <Nav className="align-items-center">
                                <Button variant="outline-light" onClick={toggleDarkMode} className="mr-2">
                                    <AiOutlineBulb size={20}/>
                                </Button>
                                <Dropdown align="end">
                                    <Dropdown.Toggle variant="outline-light" id="dropdown-basic">
                                        {userName}
                                    </Dropdown.Toggle>
                                    <Dropdown.Menu>
                                        <Dropdown.Item onClick={() => {
                                            localStorage.clear();
                                            window.location.href = '/';
                                        }}>
                                            Logout
                                        </Dropdown.Item>
                                    </Dropdown.Menu>
                                </Dropdown>
                            </Nav>
                        )}
                        {!userName && (
                            <Button variant="outline-light" onClick={handleGoogleSignIn} className="ml-auto">
                                Sign in with Google
                            </Button>
                        )}
                    </Navbar.Collapse>
                </Container>
            </Navbar>

            <Container className="mt-5">
                {!userName ? (
                    <div className="text-center">
                        <h2>Please sign in to manage your research topics.</h2>
                    </div>
                ) : (
                    <>
                        {!topic && !viewAllTopics ? (
                            <>
                                <h3>Your Research Topics</h3>
                                <div className="d-flex flex-wrap mb-3">
                                    {topics.map((topicName, index) => (
                                        <div
                                            key={index}
                                            className={`topic-card ${highlightedTopics.includes(topicName) ? 'highlight' : ''}`}
                                            onClick={() => handleTopicSelect(topicName)}
                                        >
                                            <div className="topic-icon">
                                                <AiOutlineFileAdd/>
                                            </div>
                                            <div className="topic-title">{topicName}</div>
                                        </div>
                                    ))}
                                    <div
                                        className="topic-card add-topic-card"
                                    >
                                        {isAddingTopic ? (
                                            <div>
                                                <Form.Control
                                                    type="text"
                                                    placeholder="Enter topic name"
                                                    value={newTopic}
                                                    onChange={(e) => setNewTopic(e.target.value)}
                                                />
                                                <Button variant="primary" onClick={handleAddTopic}
                                                        className="btn-modern mt-2">
                                                    Add Topic
                                                </Button>
                                            </div>
                                        ) : (
                                            <div onClick={() => setIsAddingTopic(true)}>
                                                <div className="topic-icon">
                                                    <AiOutlinePlusCircle/>
                                                </div>
                                                <div className="topic-title">Add New Topic</div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                                <div className="search-container">
                                    <Form.Control type="text" placeholder="Search DOI across topics"
                                                  onKeyDown={(e) => {
                                                      if (e.key === 'Enter') {
                                                          e.preventDefault();
                                                          handleDOISearch();
                                                      }
                                                  }}/>
                                    <Button onClick={handleDOISearch}>
                                        Search DOI
                                    </Button>
                                    <Button variant="secondary" className="ml-3" onClick={handleViewAllTopics}>
                                        View All Topics
                                    </Button>
                                </div>
                            </>
                        ) : viewAllTopics ? (
                            allTopicsData.map((topicData, index) => (
                                <div key={index} className="mt-5">
                                    <h4>{topicData.topic}</h4>
                                    <Table striped bordered hover responsive>
                                        <thead>
                                        <tr>
                                            <th style={{width: '5%'}}>No</th>
                                            <th style={{width: '25%'}}>Name</th>
                                            <th style={{width: '10%'}}>Year</th>
                                            <th style={{width: '10%'}}>Publication</th>
                                            <th style={{width: '5%'}}>Page</th>
                                            <th style={{width: '30%'}}>Summary</th>
                                            <th style={{width: '10%'}}>Abstract</th>
                                            <th className="doi-column">DOI</th>
                                            <th style={{width: '15%'}}>Author</th>
                                            <th style={{width: '10%'}}>Remarks</th>
                                            <th style={{width: '10%'}}>Actions</th>
                                        </tr>
                                        </thead>
                                        <tbody>
                                        {topicData.data.map((item, itemIndex) => (
                                            <tr key={itemIndex}>
                                                <td style={{width: '5%'}}>{item.SL_NO}</td>
                                                <td style={{width: '25%'}}>{item.NAME}</td>
                                                <td style={{width: '10%'}}>{item.YEAR}</td>
                                                <td style={{width: '10%'}}>{item.PUBLICATION}</td>
                                                <td style={{width: '5%'}}>{item.PAGE_NO}</td>
                                                <td style={{width: '30%'}}>
                                                    {item.SUMMARY ? (
                                                        <Accordion>
                                                            <Accordion.Item eventKey="0">
                                                                <Accordion.Header>Show Summary</Accordion.Header>
                                                                <Accordion.Body>
                                                                    {item.SUMMARY}
                                                                </Accordion.Body>
                                                            </Accordion.Item>
                                                        </Accordion>
                                                    ) : (
                                                        ""
                                                    )}
                                                </td>
                                                <td style={{width: '10%'}}>
                                                    {item.ABSTRACT ? (
                                                        <Accordion>
                                                            <Accordion.Item eventKey="1">
                                                                <Accordion.Header>Show Abstract</Accordion.Header>
                                                                <Accordion.Body>
                                                                    {item.ABSTRACT}
                                                                </Accordion.Body>
                                                            </Accordion.Item>
                                                        </Accordion>
                                                    ) : (
                                                        ""
                                                    )}
                                                </td>
                                                <td className="doi-column">{item.DOI}</td>
                                                <td style={{width: '15%'}}>
                                                        {editable === index ? (
                                                            <Form.Control
                                                                as="textarea"
                                                                rows={3}
                                                                value={item.AUTHOR}
                                                                onChange={(e) => handleChange(index, 'AUTHOR', e.target.value)}
                                                            />
                                                        ) : item.AUTHOR ? (
                                                            <Accordion>
                                                                <Accordion.Item eventKey="2">
                                                                    <Accordion.Header>Show Author</Accordion.Header>
                                                                    <Accordion.Body>
                                                                        {item.AUTHOR}
                                                                    </Accordion.Body>
                                                                </Accordion.Item>
                                                            </Accordion>
                                                        ) : (
                                                            ""
                                                        )}
                                                    </td>
                                                <td style={{width: '10%'}}>{item.REMARKS}</td>
                                                <td style={{width: '10%'}}>
                                                    <Button variant="warning" onClick={() => handleEdit(itemIndex)}
                                                            className="btn-modern">
                                                        <AiOutlineEdit size={20}/> Edit
                                                    </Button>
                                                    <Button variant="danger" onClick={() => handleDelete(itemIndex)}
                                                            className="ml-2 btn-modern">
                                                        Delete
                                                    </Button>
                                                </td>
                                            </tr>
                                        ))}
                                        </tbody>
                                    </Table>
                                </div>
                            ))
                        ) : (
                            <>
                                <div className="d-flex justify-content-between align-items-center mb-4">
                                    <h4>Current Topic: {topic}</h4>
                                    <div>
                                        <Button variant="secondary" onClick={() => setTopic('')} className="btn-modern">
                                            Switch Topics
                                        </Button>
                                        {isAddingTopic ? (
                                            <div className="add-topic-inline">
                                                <Form.Control
                                                    type="text"
                                                    placeholder="Enter topic name"
                                                    value={newTopic}
                                                    onChange={(e) => setNewTopic(e.target.value)}
                                                />
                                                <Button variant="primary" onClick={handleAddTopic}
                                                        className="btn-modern ml-2">
                                                    Add Topic
                                                </Button>
                                            </div>
                                        ) : (
                                            <Button variant="primary" className="ml-2 btn-modern"
                                                    onClick={handleAddTopic}>
                                                <AiOutlinePlusCircle size={20}/> Add New Topic
                                            </Button>
                                        )}
                                    </div>
                                </div>
                                <Row>
                                    <Col>
                                        <Card className="mb-4 glass-card">
                                            <Card.Header>
                                                <AiOutlineFileAdd size={24}/> Upload PDFs and Fetch by DOIs
                                            </Card.Header>
                                            <Card.Body>
                                                <Form onSubmit={handleFileSubmit}>
                                                    <Row>
                                                        <Col md={6}>
                                                            <Form.Group controlId="formFile" className="mb-3">
                                                                <Form.Label>Upload PDFs</Form.Label>
                                                                <Form.Control type="file" multiple
                                                                              onChange={handleFileChange}/>
                                                            </Form.Group>
                                                            <Button variant="primary" type="submit"
                                                                    className="btn-modern">
                                                                <AiOutlineCloudUpload size={20}/> Submit PDFs
                                                            </Button>
                                                        </Col>
                                                        <Col md={6}>
                                                            <Form.Group controlId="formDois" className="mb-3">
                                                                <Form.Label>Enter DOIs (comma-separated)</Form.Label>
                                                                <Form.Control type="text" value={dois}
                                                                              onChange={handleDoisChange}/>
                                                            </Form.Group>
                                                            <Button variant="primary" onClick={handleDoisSubmit}
                                                                    className="btn-modern">
                                                                <AiOutlineFileSearch size={20}/> Submit DOIs
                                                            </Button>
                                                        </Col>
                                                    </Row>
                                                </Form>
                                            </Card.Body>
                                        </Card>
                                        {error && <Alert variant="danger" className="mt-3">{error}</Alert>}
                                    </Col>
                                </Row>
                                <Row className="mt-5">
                                    <Col>
                                        <Table striped bordered hover responsive>
                                            <thead>
                                            <tr>
                                                <th style={{width: '5%'}}>No</th>
                                                <th style={{width: '25%'}}>Name</th>
                                                <th style={{width: '10%'}}>Year</th>
                                                <th style={{width: '10%'}}>Publication</th>
                                                <th style={{width: '5%'}}>Page</th>
                                                <th style={{width: '30%'}}>Summary</th>
                                                <th style={{width: '10%'}}>Abstract</th>
                                                <th className="doi-column">DOI</th>
                                                <th style={{width: '15%'}}>Author</th>
                                                <th style={{width: '10%'}}>Remarks</th>
                                                <th style={{width: '10%'}}>Actions</th>
                                            </tr>
                                            </thead>
                                            <tbody>
                                            {data.map((item, index) => (
                                                <tr key={index}>
                                                    <td style={{width: '5%'}}>{item.SL_NO}</td>
                                                    <td style={{width: '25%'}}>{item.NAME}</td>
                                                    <td style={{width: '10%'}}>{item.YEAR}</td>
                                                    <td style={{width: '10%'}}>{item.PUBLICATION}</td>
                                                    <td style={{width: '5%'}}>{item.PAGE_NO}</td>
                                                    <td style={{width: '30%'}}>
                                                        {editable === index ? (
                                                            <Form.Control
                                                                as="textarea"
                                                                rows={3}
                                                                value={item.SUMMARY}
                                                                onChange={(e) => handleChange(index, 'SUMMARY', e.target.value)}
                                                            />
                                                        ) : item.SUMMARY ? (
                                                            <Accordion>
                                                                <Accordion.Item eventKey="0">
                                                                    <Accordion.Header>Show Summary</Accordion.Header>
                                                                    <Accordion.Body>
                                                                        {item.SUMMARY}
                                                                    </Accordion.Body>
                                                                </Accordion.Item>
                                                            </Accordion>
                                                        ) : (
                                                            ""
                                                        )}
                                                    </td>
                                                    <td style={{width: '10%'}}>
                                                        {editable === index ? (
                                                            <Form.Control
                                                                as="textarea"
                                                                rows={3}
                                                                value={item.ABSTRACT}
                                                                onChange={(e) => handleChange(index, 'ABSTRACT', e.target.value)}
                                                            />
                                                        ) : item.ABSTRACT ? (
                                                            <Accordion>
                                                                <Accordion.Item eventKey="1">
                                                                    <Accordion.Header>Show Abstract</Accordion.Header>
                                                                    <Accordion.Body>
                                                                        {item.ABSTRACT}
                                                                    </Accordion.Body>
                                                                </Accordion.Item>
                                                            </Accordion>
                                                        ) : (
                                                            ""
                                                        )}
                                                    </td>
                                                    <td className="doi-column">{item.DOI}</td>
                                                    <td style={{width: '15%'}}>
                                                        {editable === index ? (
                                                            <Form.Control
                                                                as="textarea"
                                                                rows={3}
                                                                value={item.AUTHOR}
                                                                onChange={(e) => handleChange(index, 'AUTHOR', e.target.value)}
                                                            />
                                                        ) : item.AUTHOR ? (
                                                            <Accordion>
                                                                <Accordion.Item eventKey="2">
                                                                    <Accordion.Header>Show Author</Accordion.Header>
                                                                    <Accordion.Body>
                                                                        {item.AUTHOR}
                                                                    </Accordion.Body>
                                                                </Accordion.Item>
                                                            </Accordion>
                                                        ) : (
                                                            ""
                                                        )}
                                                    </td>
                                                    <td style={{width: '10%'}}>
                                                        {editable === index ? (
                                                            <Form.Control
                                                                as="textarea"
                                                                rows={3}
                                                                value={item.REMARKS}
                                                                onChange={(e) => handleChange(index, 'REMARKS', e.target.value)}
                                                            />
                                                        ) : (
                                                            item.REMARKS
                                                        )}
                                                    </td>
                                                    <td style={{width: '10%'}}>
                                                        {editable === index ? (
                                                            <>
                                                                <Button variant="success"
                                                                        onClick={() => handleSave(index)}
                                                                        className="btn-modern">
                                                                    <AiOutlineSave size={20}/> Save
                                                                </Button>
                                                                <Button variant="danger"
                                                                        onClick={() => handleDelete(index)}
                                                                        className="ml-2 btn-modern">
                                                                    Delete
                                                                </Button>
                                                            </>
                                                        ) : (
                                                            <Button variant="warning" onClick={() => handleEdit(index)}
                                                                    className="btn-modern">
                                                                <AiOutlineEdit size={20}/> Edit
                                                            </Button>
                                                        )}
                                                    </td>
                                                </tr>
                                            ))}
                                            </tbody>
                                        </Table>
                                    </Col>
                                </Row>
                            </>
                        )}
                    </>
                )}
            </Container>
            <ToastContainer/>
        </>
    );
};

export default App;
