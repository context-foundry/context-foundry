import React, { useState } from 'react';
import styled from 'styled-components';

const SearchContainer = styled.div`
    margin: 20px;
`;

const Input = styled.input`
    padding: 10px;
    border-radius: 5px;
    border: none;
    width: 60%;

    @media (max-width: 600px) {
        width: 80%;
    }
`;

const Button = styled.button`
    padding: 10px;
    border-radius: 5px;
    border: none;
    background-color: #007bff;
    color: white;
    cursor: pointer;

    &:hover {
        background-color: #0056b3;
    }
`;

const Search = ({ onSearch }) => {
    const [query, setQuery] = useState('');

    const handleSearch = () => {
        onSearch(query);
        setQuery('');
    };

    return (
        <SearchContainer>
            <Input 
                type="text" 
                value={query} 
                onChange={(e) => setQuery(e.target.value)} 
                placeholder="Search city..."
            />
            <Button onClick={handleSearch}>Search</Button>
        </SearchContainer>
    );
};

export default Search;