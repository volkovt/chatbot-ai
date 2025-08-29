/*
 * TokenBucketRateLimiter
 *
 * Recurso:
 * - Implementa rate limiting com balde de tokens (token bucket).
 * - Thread-safe usando ReentrantLock.
 * - Builder com parâmetros: capacity, refillTokens, refillPeriod (TimeUnit).
 * - Métodos: tryAcquire(permits), acquireBlocking(permits, timeout,...).
 * - Demonstração de uso no método main com ExecutorService.
 */

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Future;
import java.util.concurrent.Callable;
import java.util.concurrent.locks.ReentrantLock;

public class TokenBucketRateLimiter {

    private final long capacity;
    private final double refillTokens;
    private final long refillPeriodNanos;

    private double tokens;
    private long lastRefillNanos;

    private final ReentrantLock lock = new ReentrantLock();

    private TokenBucketRateLimiter(long capacity, double refillTokens, long refillPeriodNanos) {
        if (capacity <= 0) throw new IllegalArgumentException("capacity deve ser > 0");
        if (refillTokens <= 0) throw new IllegalArgumentException("refillTokens deve ser > 0");
        if (refillPeriodNanos <= 0) throw new IllegalArgumentException("refillPeriodNanos deve ser > 0");
        this.capacity = capacity;
        this.refillTokens = refillTokens;
        this.refillPeriodNanos = refillPeriodNanos;
        this.tokens = capacity;
        this.lastRefillNanos = System.nanoTime();
    }

    public static Builder newBuilder() {
        return new Builder();
    }

    private void refillIfNeeded() {
        long now = System.nanoTime();
        long elapsed = now - lastRefillNanos;
        if (elapsed <= 0) return;

        double periods = (double) elapsed / (double) refillPeriodNanos;
        if (periods >= 1e-9) {
            double toAdd = periods * refillTokens;
            tokens = Math.min(capacity, tokens + toAdd);
            lastRefillNanos = now;
        }
    }

    /**
     * Tenta adquirir 'permits' tokens sem bloquear.
     * @return true se conseguiu, false caso contrário.
     */
    public boolean tryAcquire(int permits) {
        if (permits <= 0) throw new IllegalArgumentException("permits deve ser > 0");
        lock.lock();
        try {
            refillIfNeeded();
            if (tokens >= permits) {
                tokens -= permits;
                return true;
            }
            return false;
        } finally {
            lock.unlock();
        }
    }

    /**
     * Tenta adquirir 'permits' tokens, bloqueando até 'timeout'.
     * @return true se conseguiu dentro do prazo, false caso contrário.
     */
    public boolean acquireBlocking(int permits, long timeout, TimeUnit unit) throws InterruptedException {
        if (permits <= 0) throw new IllegalArgumentException("permits deve ser > 0");
        Objects.requireNonNull(unit, "unit");
        long deadline = System.nanoTime() + unit.toNanos(timeout);
        while (true) {
            if (tryAcquire(permits)) {
                return true;
            }
            long remaining = deadline - System.nanoTime();
            if (remaining <= 0) {
                return false;
            }
            // Dorme um pedaço do período de refill para evitar busy-wait
            long sleepNanos = Math.min(remaining, refillPeriodNanos / 2);
            if (sleepNanos <= 0) sleepNanos = TimeUnit.MILLISECONDS.toNanos(1);
            TimeUnit.NANOSECONDS.sleep(sleepNanos);
        }
    }

    public long getCapacity() {
        return capacity;
    }

    public double getAvailableTokens() {
        lock.lock();
        try {
            refillIfNeeded();
            return tokens;
        } finally {
            lock.unlock();
        }
    }

    @Override
    public String toString() {
        return "TokenBucketRateLimiter{capacity=" + capacity +
                ", refillTokens=" + refillTokens +
                ", refillPeriodNanos=" + refillPeriodNanos + "}";
    }

    // -------------------- Builder --------------------
    public static class Builder {
        private long capacity = 10;
        private double refillTokens = 5.0;
        private long refillPeriodNanos = TimeUnit.SECONDS.toNanos(1);

        public Builder capacity(long c) {
            this.capacity = c;
            return this;
        }

        public Builder refill(double tokens, long period, TimeUnit unit) {
            this.refillTokens = tokens;
            this.refillPeriodNanos = unit.toNanos(period);
            return this;
        }

        public TokenBucketRateLimiter build() {
            return new TokenBucketRateLimiter(capacity, refillTokens, refillPeriodNanos);
        }
    }

    // -------------------- Demonstração --------------------
    public static void main(String[] args) throws Exception {
        TokenBucketRateLimiter limiter = TokenBucketRateLimiter
                .newBuilder()
                .capacity(12)
                .refill(6, 1, TimeUnit.SECONDS) // 6 tokens/s
                .build();

        System.out.println("Limiter: " + limiter);
        System.out.println("Tokens iniciais: " + limiter.getAvailableTokens());

        ExecutorService pool = Executors.newFixedThreadPool(3);
        List<Callable<String>> tasks = new ArrayList<>();

        // 15 tarefas que consomem de 1 a 3 tokens cada
        for (int i = 1; i <= 15; i++) {
            final int id = i;
            final int permits = 1 + (i % 3); // 1..3
            tasks.add(() -> {
                boolean ok = limiter.acquireBlocking(permits, 3, TimeUnit.SECONDS);
                if (!ok) {
                    return "Tarefa " + id + " FALHOU (sem tokens após timeout)";
                }
                // Simula algum trabalho
                TimeUnit.MILLISECONDS.sleep(200 + (id % 5) * 50);
                return "Tarefa " + id + " executada com " + permits + " tokens; tokens restantes="
                        + String.format("%.2f", limiter.getAvailableTokens());
            });
        }

        List<Future<String>> results = pool.invokeAll(tasks);
        for (Future<String> f : results) {
            System.out.println(f.get());
        }

        pool.shutdownNow();
        System.out.println("Disponível ao final: " + String.format("%.2f", limiter.getAvailableTokens()));
    }
}
