#include "StockActivity.h"

namespace infinitehorizontal {

std::optional<ThreadActivity> parseThreadActivity(const QByteArray &stat)
{
    const auto end = stat.lastIndexOf(')');
    if (stat.indexOf('(') < 0 || end < 0)
        return {};
    const auto fields = stat.mid(end + 1).simplified().split(' ');
    if (fields.size() < 20 || fields[0].size() != 1)
        return {};
    bool userValid = false, systemValid = false, startValid = false;
    const quint64 user = fields[11].toULongLong(&userValid);
    const quint64 system = fields[12].toULongLong(&systemValid);
    const quint64 start = fields[19].toULongLong(&startValid);
    if (!userValid || !systemValid || !startValid || user + system < user)
        return {};
    return ThreadActivity{user + system, start, fields[0][0]};
}

bool QuietWindow::observe(const StockActivity &activity, qint64 elapsedMilliseconds)
{
    const bool unchanged = m_previous && !m_previous->running && !activity.running
        && !activity.identities.isEmpty()
        && activity.identities == m_previous->identities
        && activity.ticks == m_previous->ticks
        && elapsedMilliseconds >= m_previousTime;
    if (!unchanged)
        m_quietSince = elapsedMilliseconds;
    m_previous = activity;
    m_previousTime = elapsedMilliseconds;
    return unchanged && elapsedMilliseconds - m_quietSince >= m_required;
}

}
