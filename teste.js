/*
PromisePool — Limitador de concorrência para Promises com:
- Concurrency configurável
- Timeout por tarefa
- Retries com backoff exponencial (ou constante)
- Callbacks de progresso (onStart, onProgress, onError, onDone)
- API: add(fn), run(), clear()

Uso básico:
const pool = new PromisePool({ concurrency: 4, timeout: 2000, retries: 2 });
pool.onProgress = (stats) => console.log(stats);
pool.add(() => fetch(...));
await pool.run();
*/

(function (global) {
  'use strict';

  class TimeoutError extends Error {
    constructor(message) {
      super(message);
      this.name = 'TimeoutError';
    }
  }

  class PromisePool {
    /**
     * @param {Object} opts
     * @param {number} opts.concurrency - tarefas simultâneas
     * @param {number|null} opts.timeout - ms; null desabilita
     * @param {number} opts.retries - tentativas extras
     * @param {'exponential'|'constant'} opts.backoffStrategy
     * @param {number} opts.backoffBase - ms base para backoff
     */
    constructor(opts = {}) {
      const {
        concurrency = 5,
        timeout = null,
        retries = 0,
        backoffStrategy = 'exponential',
        backoffBase = 200
      } = opts;

      if (concurrency <= 0) {
        throw new Error('concurrency deve ser > 0');
      }

      this.concurrency = concurrency;
      this.timeout = timeout;
      this.retries = retries;
      this.backoffStrategy = backoffStrategy;
      this.backoffBase = backoffBase;

      this._queue = [];
      this._active = 0;
      this._started = false;

      // callbacks: stats = { completed, failed, total, active }
      this.onStart = null;
      this.onProgress = null;
      this.onError = null;
      this.onDone = null;

      this._stats = { completed: 0, failed: 0, total: 0, active: 0 };
    }

    add(taskFn) {
      if (typeof taskFn !== 'function') {
        throw new Error('taskFn deve ser função que retorna Promise');
      }
      this._queue.push(taskFn);
      this._stats.total++;
      return this;
    }

    clear() {
      this._queue.length = 0;
      return this;
    }

    _emitStart() {
      if (this.onStart && !this._started) {
        this._started = true;
        try { this.onStart({ ...this._stats }); } catch (e) {}
      }
    }

    _emitProgress() {
      if (this.onProgress) {
        try { this.onProgress({ ...this._stats }); } catch (e) {}
      }
    }

    _emitError(err) {
      if (this.onError) {
        try { this.onError(err, { ...this._stats }); } catch (e) {}
      }
    }

    _emitDone() {
      if (this.onDone) {
        try { this.onDone({ ...this._stats }); } catch (e) {}
      }
    }

    async run() {
      this._emitStart();
      const results = [];
      const errors = [];
      const runners = [];

      const next = async () => {
        while (this._active < this.concurrency && this._queue.length > 0) {
          const taskFn = this._queue.shift();
          this._active++;
          this._stats.active = this._active;
          this._emitProgress();

          const runner = this._runWithRetry(taskFn)
            .then((res) => {
              results.push(res);
              this._stats.completed++;
            })
            .catch((err) => {
              errors.push(err);
              this._stats.failed++;
              this._emitError(err);
            })
            .finally(() => {
              this._active--;
              this._stats.active = this._active;
              this._emitProgress();
            });

          runners.push(runner);
        }

        if (this._active > 0 || this._queue.length > 0) {
          await Promise.race(runners).catch(() => {});
          return next();
        }
      };

      await next();
      await Promise.allSettled(runners);
      this._emitDone();

      return { results, errors, stats: { ...this._stats } };
    }

    async _runWithRetry(taskFn) {
      let attempt = 0;
      let lastErr = null;

      while (attempt <= this.retries) {
        try {
          return await this._runWithTimeout(taskFn);
        } catch (err) {
          lastErr = err;
          if (attempt >= this.retries) break;
          await this._backoff(attempt);
          attempt++;
        }
      }
      throw lastErr;
    }

    async _runWithTimeout(taskFn) {
      if (this.timeout == null) {
        return taskFn();
      }
      let timer;
      try {
        return await new Promise((resolve, reject) => {
          let finished = false;
          timer = setTimeout(() => {
            if (finished) return;
            finished = true;
            reject(new TimeoutError('Tarefa excedeu o tempo limite'));
          }, this.timeout);

          Promise.resolve()
            .then(taskFn)
            .then((val) => {
              if (finished) return;
              finished = true;
              resolve(val);
            })
            .catch((err) => {
              if (finished) return;
              finished = true;
              reject(err);
            });
        });
      } finally {
        if (timer) clearTimeout(timer);
      }
    }

    async _backoff(attempt) {
      const base = this.backoffBase;
      let wait = base;
      if (this.backoffStrategy === 'exponential') {
        wait = base * Math.pow(2, attempt);
      }
      await new Promise((r) => setTimeout(r, wait));
    }
  }

  // Export
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { PromisePool, TimeoutError };
  } else {
    global.PromisePool = PromisePool;
    global.TimeoutError = TimeoutError;
  }

  // -------------------- Demonstração --------------------
  async function demo() {
    const isNode = typeof process !== 'undefined' && process?.versions?.node;
    if (!isNode) return; // Evita rodar no browser automaticamente

    const { PromisePool } = module.exports;

    const pool = new PromisePool({
      concurrency: 3,
      timeout: 1200,
      retries: 2,
      backoffStrategy: 'exponential',
      backoffBase: 150
    });

    pool.onStart = (s) => console.log('[start]', s);
    pool.onProgress = (s) => console.log('[progress]', s);
    pool.onError = (err, s) => console.log('[error]', err.message, s);
    pool.onDone = (s) => console.log('[done]', s);

    // Cria 10 tarefas que levam 200-800ms e falham algumas vezes
    for (let i = 0; i < 10; i++) {
      const id = i + 1;
      pool.add(async () => {
        const delay = 200 + (id % 5) * 150;
        await new Promise((r) => setTimeout(r, delay));
        // Simula falhas intermitentes
        if (id % 4 === 0 && Math.random() < 0.6) {
          throw new Error(`Falha simulada na tarefa ${id}`);
        }
        return `OK ${id} (delay=${delay}ms)`;
      });
    }

    const { results, errors, stats } = await pool.run();
    console.log('Resultados:', results);
    console.log('Erros:', errors.map(e => e.message));
    console.log('Stats finais:', stats);
  }

  demo();

})(typeof globalThis !== 'undefined' ? globalThis : window);
