import http from 'k6/http';
import { check } from 'k6';
import { BASE_URL } from '../config.js';

export const options = {
    vus: 1,
    duration: '10s',
};

export default function () {
    const response = http.get(`${BASE_URL}/chain/cpu`, {
        tags: { scenario: 'chain-cpu' },
    });

    check(response, {
        'status is 200': (r) => r.status === 200,
    });
}