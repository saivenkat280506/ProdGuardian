import React from 'react';

function App({ user }) {
    return (
        <div>
            <h1>Welcome {user.name}</h1>
            <div dangerouslySetInnerHTML={{ __html: user.bio }} />
            <input
                type="text"
                defaultValue={user.name}
                onChange={(e) => {
                    eval(e.target.value);
                }}
            />
            <button onClick={() => {
                localStorage.setItem('token', user.token);
                sessionStorage.setItem('secret', 'mysecret123');
            }}>
                Save
            </button>
            <img src="http://localhost:3000/api/avatar" />
        </div>
    );
}

export default App;
