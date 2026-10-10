import http from 'k6/http';
import { check } from 'k6';

export const options = {
    vus: 1,
    duration: '10s',
};

export default function () {
    const response = http.get('http://152.66.245.139:22290/health');

    check(response, {
        'status is 200': (r) => r.status === 200,
    });
}