import discord
from discord.ext import commands

async def safe_send(ctx_or_channel, content=None, **kwargs):
    """Rate Limit 안전한 메시지 전송"""
    try:
        if hasattr(ctx_or_channel, 'send'):
            return await ctx_or_channel.send(content, **kwargs)
        else:
            return await ctx_or_channel.send(content, **kwargs)
    except Exception as e:
        print(f"메시지 전송 실패: {e}")
        return None

class HelloCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.command(name='안녕', help='봇이 인사해요!')
    async def hello(self, ctx: commands.Context):
        await safe_send(ctx, f'안녕하세요 {ctx.author.mention}님! 🎮\n롤, 발로란트, 오버워치의 이스포츠 뉴스를 알려드릴게요!')
    
    @commands.command(name='핑', help='봇의 응답속도를 알려줍니다.')
    async def ping(self, ctx: commands.Context):
        latency = round(ctx.bot.latency * 1000)
        await safe_send(ctx, f'🏓 퐁! 응답속도: **{latency}ms**')

async def setup(bot: commands.Bot):
    await bot.add_cog(HelloCommand(bot))