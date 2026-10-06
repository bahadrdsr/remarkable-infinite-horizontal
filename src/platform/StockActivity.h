#pragma once

#include <QByteArray>
#include <QStringList>
#include <optional>

namespace infinitehorizontal {

struct ThreadActivity {
    quint64 ticks = 0;
    quint64 started = 0;
    char state = 0;
};

std::optional<ThreadActivity> parseThreadActivity(const QByteArray &stat);

struct StockActivity {
    QStringList identities;
    quint64 ticks = 0;
    bool running = false;
};

class QuietWindow
{
public:
    explicit QuietWindow(qint64 requiredMilliseconds) : m_required(requiredMilliseconds) {}
    bool observe(const StockActivity &activity, qint64 elapsedMilliseconds);

private:
    qint64 m_required;
    qint64 m_quietSince = 0;
    qint64 m_previousTime = -1;
    std::optional<StockActivity> m_previous;
};

}
